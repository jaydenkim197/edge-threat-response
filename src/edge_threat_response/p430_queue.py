"""Run and collect the fixed four-node P430 experiment queue."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from .p430_workflow import NODES, now, read, save, sha

TERMINAL = {"COMPLETED", "FAILED", "BLOCKED", "SKIPPED"}
STATES = TERMINAL | {"PENDING", "RUNNING", "WAITING_FOR_DATA"}
JOBS = ("train", "eval", "noaug-train", "noaug-eval")
FOLLOWUPS = {"zoom": ("zoom", "WAITING_FOR_DATA"),
             "hoi-g": ("hoi", "BLOCKED"), "hoi-vg": ("hoi", "BLOCKED")}


@contextmanager
def process_lock(path):
    with path.open("a+b") as stream:
        if not path.stat().st_size:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            from msvcrt import LK_NBLCK, locking
            locking(stream.fileno(), LK_NBLCK, 1)
        else:
            from fcntl import LOCK_EX, LOCK_NB, flock
            flock(stream.fileno(), LOCK_EX | LOCK_NB)
        yield


def alive(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # An access failure is inconclusive.
        try:
            code = wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def candidate_metrics(value):
    point = value["point"]
    negative = value["negative_frames"]
    return {**{key: value[key] for key in ("checkpoint", "checkpoint_sha256", "ap50", "ap50_95",
                                          "total_small_960", "total_positive", "negative_frames")},
            "point": point, "recall": point["tp"] / value["total_positive"],
            "small_recall": point["small_tp"] / value["total_small_960"],
            "fp_negative_per100": 100 * point["negative_frames_flagged"] / negative}


def choose_noaug(nodes):
    evaluated = {node: nodes.get(node, {}).get("eval", {}) for node in NODES}
    if any(record.get("status") not in TERMINAL for record in evaluated.values()):
        return {"status": "PENDING"}
    eligible = []
    for lr in sorted({pair[1] for pair in NODES.values()}):
        members = [evaluated[node] for node, (_, rate) in NODES.items() if rate == lr]
        if any(item["status"] != "COMPLETED" for item in members):
            continue
        gains = []
        for item in members:
            baseline, selected = item["baseline"], item["selected"]
            gain = selected["small_recall"] - baseline["small_recall"]
            # Require a gain on both sessions and cap loss of overall recall at two points.
            if (gain <= 0 or selected["recall"] < baseline["recall"] - .02
                    or selected["fp_negative_per100"] > 1):
                break
            gains.append(gain)
        if len(gains) == 2:
            eligible.append((min(gains), sum(gains), -lr))
    if not eligible:
        return {"status": "SKIPPED", "reason": "No learning rate passed both development sessions"}
    return {"status": "COMPLETED", "lr": -max(eligible)[2], "comparison": "same fold and LR with augmentation disabled"}


def aggregate(work, nodes):
    decision_file = work / "decision.json"
    if decision_file.exists():
        decision = read(decision_file)
    else:
        decision = choose_noaug(nodes)
        if decision["status"] != "PENDING":
            save(decision_file, decision)
    base = [nodes.get(node, {}).get("eval", {}).get("status") for node in NODES]
    noaug = [nodes.get(node, {}).get("noaug-eval", {}).get("status") for node in NODES]
    closed = all(status in TERMINAL for status in base + noaug)
    ready = sum(status == "COMPLETED" for status in base)
    summary = {
        "updated_at": now(), "nodes": nodes,
        "stage_a": "COMPLETED" if closed and ready == len(NODES) else "FAILED" if closed else "RUNNING",
        "stage_b": "COMPLETED" if (work / "prior-alternatives.json").is_file() else "BLOCKED",
        "stage_c": nodes.get("pc13", {}).get("zoom", {}).get("status", "WAITING_FOR_DATA"),
        "stage_d": {key: nodes.get("pc13", {}).get(key, {}).get("status", "BLOCKED") for key in ("hoi-g", "hoi-vg")},
        "stage_e": ("COMPLETED" if ready else "BLOCKED") if closed else "PENDING",
        "scope": "development", "final_test_used": False, "final_detector_selected": False,
        "augmentation_decision": decision,
    }
    save(work / "experiment_status.json", summary)
    return decision


def collect(work, port):
    keys = read(work / "coordinator.json")
    if set(keys) != set(NODES) or any(not isinstance(token, str) or len(token) < 32 for token in keys.values()):
        raise ValueError("Coordinator needs a private token for each worker")
    state_dir = work / "node-receipts"
    state_dir.mkdir(exist_ok=True)
    nodes = {node: read(state_dir / f"{node}.json") for node in NODES
             if (state_dir / f"{node}.json").exists()}
    aggregate(work, nodes)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(4)

        def log_message(self, *_):
            pass

        def do_POST(self):
            node = self.path.removeprefix("/v1/")
            expected = keys.get(node)
            if not expected or not compare_digest("Bearer " + expected, self.headers.get("Authorization", "")):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32_768 or self.headers.get("Transfer-Encoding"):
                    raise ValueError("Incorrect status length")
                payload = json.loads(self.rfile.read(length))
                allowed = set(JOBS) | (set(FOLLOWUPS) if node == "pc13" else set())
                if not isinstance(payload, dict) or set(payload) - allowed or any(
                    not isinstance(item, dict) or item.get("status") not in STATES for item in payload.values()
                ):
                    raise ValueError("Invalid worker status")
                if set(nodes.get(node, {})) - set(payload):
                    raise ValueError("Worker state cannot discard jobs")
                previous = nodes.get(node, {})
                if any(previous.get(job, {}).get("status") in {"COMPLETED", "SKIPPED"}
                       and previous[job] != record for job, record in payload.items()):
                    raise ValueError("Worker state cannot change a completed job")
                pending = {**nodes, node: payload}
                decision = aggregate(work, pending)
                if payload != previous:
                    save(state_dir / f"{node}.json", payload)
                nodes[node] = payload
                body = json.dumps(decision).encode("utf-8")
            except (ValueError, TypeError, KeyError, ZeroDivisionError):
                self.send_error(400)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Collector PID {os.getpid()}, loopback port {port}", flush=True)
        server.serve_forever()


class Worker:
    def __init__(self, work, node):
        self.work = work
        self.node = node
        self.config = read(work / "node.json")
        self.history = work / "worker-status.json"
        self.jobs = read(self.history) if self.history.exists() else {}
        self.decision = {"status": "PENDING"}
        self.mutex = threading.Lock()
        self.shutdown = threading.Event()

    def record(self, step, status, **details):
        with self.mutex:
            if self.jobs.get(step, {}).get("status") == status and all(
                self.jobs[step].get(key) == value for key, value in details.items()
            ):
                return
            self.jobs[step] = {"status": status, "at": now(), **details}
            save(self.history, self.jobs)

    def exchange(self):
        with self.mutex:
            snapshot = dict(self.jobs)
        for job, record in list(snapshot.items()):
            if record.get("status") == "RUNNING":
                progress = self.work / record["run_id"] / f"attempt-{record['attempt']:02d}" / "progress.json"
                if progress.is_file():
                    try:
                        snapshot[job] = {**record, "progress": read(progress)}
                    except OSError:
                        pass
        request = Request(f"{self.config['coordinator']}/v1/{self.node}", data=json.dumps(snapshot).encode(),
                          headers={"Authorization": "Bearer " + self.config["token"],
                                   "Content-Type": "application/json"})
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=6) as response:
                decision = json.load(response)
        except (URLError, TimeoutError, OSError):
            return False
        with self.mutex:
            self.decision = decision
        return True

    def heartbeat(self):
        while not self.shutdown.is_set():
            self.exchange()
            self.shutdown.wait(15)

    def local_run(self, step, training=None):
        run_id = f"{self.work.name}-{self.node}-{step}"
        home = self.work / run_id
        home.mkdir(exist_ok=True)
        slots = sorted(home.glob("attempt-*"))
        if slots:
            slot = slots[-1]
            receipt = slot / "exit.json"
            child = slot / "child.json"
            current = self.jobs.get(step, {})
            pid = read(child)["pid"] if child.exists() else current.get("pid")
            while pid and alive(pid) and not receipt.exists():
                time.sleep(3)
            if receipt.exists():
                previous = read(receipt)
                if previous["code"] == 0:
                    result = slot / "result.json"
                    if sha(result) != previous["result_sha256"]:
                        self.record(step, "FAILED", run_id=run_id, reason="Stored result checksum changed")
                        return None
                    return slot
                if previous["code"] != 75:
                    self.record(step, "FAILED", run_id=run_id, reason="Stage failed", exit_code=previous["code"])
                    return None
            # Retry a lost worker or a GPU contention once. Preserve the original files.
            if len(slots) >= 2:
                self.record(step, "BLOCKED", run_id=run_id, reason="Retry budget exhausted after interruption or busy GPU")
                return None
            lock = self.work.parent / "training/gpu0-training.lock"
            if lock.is_file() and not receipt.exists():
                owner = read(lock)
                if owner.get("owner") == run_id and not alive(owner["pid"]):
                    lock.unlink()
        attempt = len(slots) + 1
        slot = home / f"attempt-{attempt:02d}"
        slot.mkdir()
        command = [sys.executable, "-u", "-m", __spec__.name, str(self.work), "child",
                   self.node, step, str(slot)]
        if training is not None:
            command.extend(("--training", str(training)))
        save(slot / "invocation.json", {
            "run_id": run_id, "command": command, "started_at": now(), "gpu_id": 0,
            "git_commit": self.config["git_commit"], "node": self.node,
        })
        with (slot / "stdout.log").open("xb") as stdout, (slot / "stderr.log").open("xb") as stderr:
            child = subprocess.Popen(command, cwd=self.work.parent.parent, stdout=stdout, stderr=stderr,
                                     stdin=subprocess.DEVNULL)
            self.record(step, "RUNNING", run_id=run_id, attempt=attempt, pid=child.pid)
            code = child.wait()
        if code == 75:
            if attempt == 1:
                self.shutdown.wait(15)
            return self.local_run(step, training)
        if code or not (slot / "exit.json").is_file():
            self.record(step, "FAILED", run_id=run_id, reason="Stage process stopped", exit_code=code)
            return None
        return slot

    def run_job(self, step, training=None):
        previous = self.jobs.get(step, {})
        if previous.get("status") in {"FAILED", "SKIPPED"}:
            return None
        if (self.work / "pause.request").exists() and previous.get("status") != "COMPLETED":
            return None
        slot = self.local_run(step, training)
        if slot is None:
            return None
        if previous.get("status") == "COMPLETED":
            return slot
        result = read(slot / "result.json")
        details = {"run_id": slot.parent.name, "attempt": int(slot.name[-2:]), "receipt_sha256": sha(slot / "result.json")}
        if step.endswith("eval"):
            details.update(baseline=candidate_metrics(result["baseline"]), selected=candidate_metrics(result["selected"]),
                           scored_checkpoints=sum(len(row["aliases"]) for row in result["ranked"]),
                           final_test_used=False)
        self.record(step, "COMPLETED", **details)
        return slot

    def main(self):
        print(f"Worker {self.node} PID {os.getpid()}", flush=True)
        heartbeat = threading.Thread(target=self.heartbeat, daemon=True)
        heartbeat.start()
        try:
            stages = JOBS + (tuple(FOLLOWUPS) if self.node == "pc13" else ())
            for step in stages:
                if step not in self.jobs:
                    folder, waiting = FOLLOWUPS.get(step, ("", "PENDING"))
                    missing = folder and not (self.work / folder / "approval.json").is_file()
                    self.record(step, waiting if missing else "PENDING")
            train = self.run_job("train")
            if train is None and self.jobs["train"]["status"] in TERMINAL:
                self.record("eval", "BLOCKED", reason="Training did not complete")
            elif train is not None:
                self.run_job("eval", train)
            while self.decision["status"] == "PENDING" and not (self.work / "pause.request").exists():
                self.shutdown.wait(5)
            if not (self.work / "pause.request").exists():
                if self.decision.get("lr") == NODES[self.node][1]:
                    noaug = self.run_job("noaug-train")
                    if noaug is not None:
                        self.run_job("noaug-eval", noaug)
                    elif self.jobs["noaug-train"]["status"] in TERMINAL:
                        self.record("noaug-eval", "BLOCKED", reason="Training did not complete")
                else:
                    for step in JOBS[2:]:
                        self.record(step, "SKIPPED", reason="This condition did not pass the paired selection gate")
            if self.node == "pc13":
                self.run_approved_inputs()
            while not (self.work / "pause.request").exists() and not self.exchange():
                self.shutdown.wait(15)
        finally:
            self.shutdown.set()
            heartbeat.join(timeout=8)
            self.exchange()

    def run_approved_inputs(self):
        while not (self.work / "pause.request").exists():
            for step, (folder, waiting) in FOLLOWUPS.items():
                if self.jobs.get(step, {}).get("status") in {"COMPLETED", "FAILED"}:
                    continue
                if (self.work / folder / "approval.json").is_file():
                    self.run_job(step)
                else:
                    self.record(step, waiting, reason="Waiting for a human-reviewed approved manifest")
            if all(self.jobs.get(step, {}).get("status") in {"COMPLETED", "FAILED"} for step in FOLLOWUPS):
                break
            self.shutdown.wait(30)


def run_child(work, node, stage, slot, training):
    from . import p430_workflow

    save(slot / "child.json", {"pid": os.getpid(), "started_at": now()})
    args = [str(work), node, stage, str(slot)]
    if training is not None:
        args.extend(("--training", str(training)))
    sys.argv[1:] = args
    try:
        code = p430_workflow.main() or 0
    except BaseException:
        save(slot / "exit.json", {"code": 1, "finished_at": now()})
        raise
    receipt = {"code": code, "finished_at": now()}
    if not code:
        receipt["result_sha256"] = sha(slot / "result.json")
    save(slot / "exit.json", receipt)
    return code


def launch(work, action, remainder):
    flags = 0x01000000 | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    sequence = str(time.time_ns())
    with (work / (action + "-" + sequence + ".log")).open("xb") as log:
        process = subprocess.Popen([sys.executable, "-u", "-m", __spec__.name, str(work), action, *remainder],
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=flags, start_new_session=os.name != "nt",
                                   env={**os.environ, "YOLO_AUTOINSTALL": "false", "PYTHONUTF8": "1",
                                        "KMP_DUPLICATE_LIB_OK": "TRUE"})
    print(process.pid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("mode", choices=("worker", "collect", "launch", "child"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    if ns.mode == "launch":
        action, *rest = ns.args
        if action not in {"worker", "collect"}:
            parser.error("Launch a worker or collector")
        launch(ns.work, action, rest)
    elif ns.mode == "child":
        job = argparse.ArgumentParser()
        job.add_argument("node", choices=NODES)
        job.add_argument("stage")
        job.add_argument("slot", type=Path)
        job.add_argument("--training", type=Path)
        phase = job.parse_args(ns.args)
        return run_child(ns.work, phase.node, phase.stage, phase.slot, phase.training)
    else:
        with process_lock(ns.work / (ns.mode + ".lock")):
            if ns.mode == "worker":
                Worker(ns.work, ns.args[0]).main()
            else:
                collect(ns.work, int(ns.args[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
