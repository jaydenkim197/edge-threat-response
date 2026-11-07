"""One-off PC13 M2 completion -> frozen comparisons. Never touches review DBs.

Uses existing evaluation environment/tools; no new service or scheduled task.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Class6\edge-threat-response")
SOURCE = Path(r"C:\Class6\etr-worktrees\m2-20261107-run")
OUTPUT = ROOT/"runs/m2-followup-20261107-v2"
EVIDENCE = ROOT/"runs/m2-preparation-20261107/followup-v2"
sys.path[:0] = [str(SOURCE/"src"), str(SOURCE/"tools")]
import finish_raw_training as followup
from edge_threat_response.training import _sha256_file, _write_json, _git_commit, gpu_training_lock


def preflight():
    result = followup.preflight_environment()
    reference = ROOT/"runs/raw-followup-20261106-recovery-v1/ap/models.json"
    followup.reference_cases(reference, ["custom-n-640", "raw-m1-n-640", "coco-n-640"])
    expanded = ROOT/"runs/reviewed-cctv-20261106-v2/suite.json"
    suite = json.loads(expanded.read_text())
    data = suite["datasets"]["us-mock-reviewed"]
    if data["images"] != 83 or data["knife_objects"] != 31:
        raise ValueError("Expected immutable expanded CCTV development suite")
    if _sha256_file(Path(data["truth"])) != data["truth_sha256"]:
        raise ValueError("Expanded CCTV truth changed")
    for path, digest in suite["inputs"].items():
        if _sha256_file(Path(path)) != digest:
            raise ValueError("Expanded CCTV input changed")
    return {**result, "reference_models_sha256": _sha256_file(reference),
            "expanded_suite_sha256": _sha256_file(expanded)}


def main():
    readiness = preflight()
    if "--preflight-only" in sys.argv:
        print(json.dumps(readiness))
        return
    # A detached launch is claimed exactly once, including failed launches.
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (EVIDENCE/"followup-worker-claim").open("x"):
        pass
    sys.stdout = (EVIDENCE/"followup-worker.log").open("x", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout
    state = {"status": "waiting_for_training", "source_commit": _git_commit(),
             "worker_sha256": _sha256_file(Path(__file__)), "preflight": readiness,
             "final_detector_selected": False, "review_database_modified": False}

    def record(**fields):
        state.update(fields, updated_at_utc=datetime.now(timezone.utc).isoformat())
        _write_json(EVIDENCE/"followup-worker-state.json", state)

    try:
        record()
        followup.finish(ROOT, ROOT/"data/processed/m2-real-20261107-v1-profiles/queue.json", OUTPUT, 36,
            reference_models=ROOT/"runs/raw-followup-20261106-recovery-v1/ap/models.json",
            reference_ids=["custom-n-640", "raw-m1-n-640", "coco-n-640"])
        record(status="evaluating_expanded_cctv")
        extra = OUTPUT/"cctv-expanded"
        extra.mkdir()
        suite = ROOT/"runs/reviewed-cctv-20261106-v2/suite.json"
        protocol = json.loads((OUTPUT/"predict/models.json").read_text())
        protocol.update(suite_sha256=_sha256_file(suite),
            experiment="same expanded opened CCTV83; not independent final evaluation")
        _write_json(extra/"models.json", protocol)
        env = {**os.environ, "PYTHONPATH": str(SOURCE/"src"), "YOLO_AUTOINSTALL": "false", "PYTHONUTF8": "1"}
        with gpu_training_lock(ROOT/"runs/training/gpu0-training.lock", owner="m2-expanded-cctv"):
            for case in protocol["cases"]:
                with (extra/(case["id"]+".log")).open("x", encoding="utf-8") as log:
                    subprocess.run([sys.executable, str(SOURCE/"tools/run_detector_comparison.py"),
                        "--suite", str(suite), "--models", str(extra/"models.json"), "--case", case["id"],
                        "--output", str(extra/"models"/case["id"]), "--authorize-development-comparison"],
                        cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            with (extra/"aggregate.log").open("x", encoding="utf-8") as log:
                subprocess.run([sys.executable, str(SOURCE/"tools/summarize_detector_comparison.py"),
                    "--suite", str(suite), "--models", str(extra/"models.json"), "--runs", str(extra/"models"),
                    "--output", str(extra/"aggregate")], cwd=SOURCE, env=env, stdout=log,
                    stderr=subprocess.STDOUT, check=True)
        record(status="passed", comparison_scope="opened development only; no D* or final claim")
    except BaseException as error:
        record(status="failed", error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
