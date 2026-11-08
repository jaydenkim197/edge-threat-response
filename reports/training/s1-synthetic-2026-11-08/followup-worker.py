"""One-off S1 completion -> the frozen M1/M2 seven-dataset comparison.

Uses existing inference, aggregation and confidence/paired analysis tools.
Stops on failed/changed training; never alters review data, truth, or D*.
"""
import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Class6\edge-threat-response")
SOURCE = Path(r"C:\Class6\etr-worktrees\s1-20261108-run")
OUTPUT = ROOT/"runs/s1-comparison-20261108-v1"
QUEUE = ROOT/"data/processed/s1-synthetic-20261108-v2-profiles/queue.json"
sys.path[:0] = [str(SOURCE/"src"), str(SOURCE/"tools")]
from edge_threat_response.training import _sha256_file, _write_json, _git_commit, gpu_training_lock


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def preflight():
    old_path = SOURCE/"reports/evaluation/m2-variants-2026-11-07/evaluation-worker.py"
    spec = importlib.util.spec_from_file_location("frozen_m2_comparison", old_path)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    suite, reference, cases, _, unique = previous.prepare()
    selected = [c for c in cases if c["id"] in {"custom-n-640", "raw-m1-n-640", "raw-m2-n-640"}]
    if len(selected) != 3 or len(suite["datasets"]) != 7 or unique != 325:
        raise ValueError("Frozen M1/M2 comparison changed")
    queue = load(QUEUE)
    if [c["recipe"] for c in queue["queue"]] != ["RAW-S1-n"]:
        raise ValueError("Expected only explicitly authorized RAW-S1-n")
    return previous, suite, reference, selected, queue, _sha256_file(old_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    previous, suite, reference, cases, queue, previous_hash = preflight()
    if args.preflight_only:
        print(json.dumps({"status": "passed", "datasets": 7, "unique_images": 325,
            "reference_cases": [c["id"] for c in cases], "queue_sha256": _sha256_file(QUEUE)}))
        return
    OUTPUT.mkdir(parents=True, exist_ok=False)
    queue_hash = _sha256_file(QUEUE)
    status = {"status": "waiting_for_training", "source_commit": _git_commit(),
        "worker_sha256": _sha256_file(Path(__file__)), "reused_comparison_worker_sha256": previous_hash,
        "queue_sha256": queue_hash, "datasets": 7, "unique_images": 325,
        "final_detector_selected": False, "review_database_modified": False, "orin_verified": False}

    def record(**fields):
        status.update(fields, updated_at_utc=datetime.now(timezone.utc).isoformat())
        _write_json(OUTPUT/"state.json", status)

    try:
        record()
        deadline = time.monotonic()+36*3600
        state_path = ROOT/"runs/training"/(queue["suite_id"]+"-queue-state.json")
        while True:
            if _sha256_file(QUEUE) != queue_hash:
                raise ValueError("S1 queue changed during wait")
            if time.monotonic() > deadline:
                raise TimeoutError("S1 wait exceeded 36h; training was not stopped")
            if state_path.exists():
                try:
                    training = load(state_path)
                except json.JSONDecodeError:
                    time.sleep(.1)
                    continue
                if training.get("queue_sha256") != queue_hash:
                    raise ValueError("Different training queue state")
                if training.get("status") == "failed":
                    raise RuntimeError("S1 training failed; no evaluation launched")
                if training.get("status") == "passed":
                    break
            time.sleep(15)
        config = load(Path(queue["queue"][0]["config"]))
        invocation_path = ROOT/"runs/training"/(config["run_name"]+"-invocation.json")
        invocation = load(invocation_path)
        if (invocation.get("status") != "passed"
                or invocation.get("observed_optimizer_updates") != queue["planned_updates_each"]):
            raise ValueError("S1 did not complete its actual update budget")
        weight = Path(invocation["save_dir"])/"weights/best.pt"
        digest = _sha256_file(weight)
        if not any(a["sha256"] == digest and Path(a["path"]).name == "best.pt" for a in invocation["artifacts"]):
            raise ValueError("S1 checkpoint differs from training artifact")
        template = next(c for c in cases if c["id"] == "raw-m2-n-640")
        cases.append({**template, "id": "raw-s1-n-640", "checkpoint": str(weight),
            "checkpoint_sha256": digest, "training_invocation_sha256": _sha256_file(invocation_path)})
        _write_json(OUTPUT/"suite.json", suite)
        _write_json(OUTPUT/"training-invocation.json", invocation)
        env = {**os.environ, "PYTHONPATH": str(SOURCE/"src"), "PYTHONUTF8": "1", "YOLO_AUTOINSTALL": "false"}
        while (ROOT/"runs/training/gpu0-training.lock").exists():
            if time.monotonic() > deadline:
                raise TimeoutError("GPU still claimed after S1 completion")
            time.sleep(1)
        with gpu_training_lock(ROOT/"runs/training/gpu0-training.lock", owner="s1-comparison"):
            for track in ("predict", "ap"):
                dest = OUTPUT/track
                dest.mkdir()
                selected = [{**c, "ultralytics_multi_label": track == "ap"} for c in cases]
                protocol = {**reference, "cases": selected, "track": track,
                    "suite_sha256": _sha256_file(OUTPUT/"suite.json"), "training_started": False,
                    "policy": {**reference["policy"], "comparison": "S1 vs frozen M1/M2 opened development; not final test"}}
                _write_json(dest/"models.json", protocol)
                (dest/"models").mkdir()
                for case in selected:
                    record(status="evaluating", active=case["id"], track=track)
                    with (dest/(case["id"]+".log")).open("x", encoding="utf-8") as log:
                        subprocess.run([sys.executable, str(SOURCE/"tools/run_detector_comparison.py"),
                            "--suite", str(OUTPUT/"suite.json"), "--models", str(dest/"models.json"),
                            "--case", case["id"], "--output", str(dest/"models"/case["id"]),
                            "--authorize-development-comparison"], cwd=SOURCE, env=env,
                            stdout=log, stderr=subprocess.STDOUT, check=True)
                with (dest/"aggregate.log").open("x", encoding="utf-8") as log:
                    subprocess.run([sys.executable, str(SOURCE/"tools/summarize_detector_comparison.py"),
                        "--suite", str(OUTPUT/"suite.json"), "--models", str(dest/"models.json"),
                        "--runs", str(dest/"models"), "--output", str(dest/"aggregate")],
                        cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
                record(status="thresholds", active=None, track=track)
                previous.curves(suite, selected, dest/"models", dest, track)
                # Re-running references must reproduce the existing comparison.
                old_csv = ROOT/"runs/m2-variants-comparison-20261107-v1"/track/"aggregate/comparison.csv"
                old_rows = {(r["dataset"], r["model"]): r for r in csv.DictReader(old_csv.open(encoding="utf-8-sig"))}
                new_rows = list(csv.DictReader((dest/"aggregate/comparison.csv").open(encoding="utf-8-sig")))
                verified = 0
                for row in new_rows:
                    if row["model"] == "raw-s1-n-640":
                        continue
                    old = old_rows[(row["dataset"], row["model"])]
                    for key in ("images", "knife_gt", "tp", "fp", "fn", "small_tp"):
                        if row[key] != old[key]:
                            raise ValueError("Reference fixed metrics did not reproduce: "+key)
                    if abs(float(row["ap50"])-float(old["ap50"])) > 1e-6:
                        raise ValueError("Reference AP50 did not reproduce")
                    verified += 1
                if verified != 21:
                    raise ValueError("Missing reference reproduction rows")
                _write_json(dest/"reference-reproduction.json", {"status": "passed", "partitions": verified,
                    "source_csv_sha256": _sha256_file(old_csv)})
        for path, expected in suite["inputs"].items():
            if _sha256_file(Path(path)) != expected:
                raise ValueError("Frozen comparison input changed")
        table = list(csv.DictReader((OUTPUT/"predict/aggregate/comparison.csv").open(encoding="utf-8-sig")))
        text = ["# S1 합성 보강 대 M1·M2 공통 개발 평가", "",
            "S1 학습 완료와 best.pt SHA, 기존 7개 개발셋의 동일 입력·AP/predict 두 경로를 확인했다.",
            "기존 기준 21개 partition × 2경로의 fixed 지표/AP50 재현을 확인했다. D0는 과거 custom 기준이며 M1·M2와 구분한다.",
            "합성 자료 보강과 전체 recipe의 개발 비교다. 독립 실제 CCTV/사건/Orin 성능 또는 최종 모델 채택을 뜻하지 않는다.",
            "US Mock 기존21장과 확대83장은 서로 겹치므로 합산하지 않는다. synthetic 평가도 실사와 합산하지 않는다.", "",
            "| Dataset | Model | AP50 | Precision .25 | Recall .25 | F1 .25 | TP | FP | FN |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for row in table:
            text.append("| "+" | ".join([row["dataset"], row["model"],
                *[f"{float(row[k]):.4f}" if row[k] else "—" for k in ("ap50", "precision025", "recall025", "f1_025")],
                row["tp"], row["fp"], row["fn"]])+" |")
        text += ["", "원시 위치: predict/ap 각각 aggregate/comparison.csv, thresholds.csv, paired-vs-m1-m2.json, models/*/summary.json과 predictions.jsonl.",
            "훈련 source/설정/승인/실제 update/weight SHA는 training-invocation.json과 state.json에 보관한다.", ""]
        (OUTPUT/"report.md").write_text("\n".join(text), encoding="utf-8")
        record(status="passed", active=None, track=None, partitions=56, reference_partitions_reproduced=42)
    except BaseException as error:
        record(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    print(json.dumps(status))


if __name__ == "__main__":
    main()
