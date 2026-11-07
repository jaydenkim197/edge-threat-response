"""After the raw queue passes, compare checkpoints on the frozen opened suite.

This is a one-off dependent batch stage, not a recurring service. It never
adopts D*, tunes on final CCTV data, or updates the production review site.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import math
import csv
import importlib.metadata
from contextlib import ExitStack
from pathlib import Path

from edge_threat_response.detector_comparison import select_f2_operating_point
from edge_threat_response.training import _sha256_file, _write_json, _git_commit, gpu_training_lock


def preflight_environment():
    packages = {}
    for name in ("torch", "torchvision", "ultralytics", "rfdetr", "pycocotools", "safetensors", "transformers", "timm"):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError("Use the existing .venv-evaluation-20261104 environment; missing "+name) from exc
    return {"status": "passed", "python": sys.executable, "packages": packages}


def reference_cases(path: Path, ids: list[str]) -> list[dict]:
    protocol = json.loads(path.read_text(encoding="utf-8-sig"))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Select explicit unique reference cases")
    cases = {c["id"]: c for c in protocol["cases"]}
    selected = []
    for case_id in ids:
        if case_id not in cases:
            raise ValueError("Unknown frozen reference case: "+case_id)
        case = dict(cases[case_id])
        if _sha256_file(Path(case["checkpoint"])) != case["checkpoint_sha256"]:
            raise ValueError("Frozen reference checkpoint changed")
        selected.append(case)
    if "custom-n-640" not in ids:
        raise ValueError("The common aggregate requires its frozen custom-n-640 reference")
    return selected


def finish(root: Path, queue_path: Path, output: Path, wait_hours: float,
           *, reference_models: Path | None = None, reference_ids: list[str] | None = None):
    if not math.isfinite(wait_hours) or not 0 < wait_hours <= 72:
        raise ValueError("Wait limit must be finite and in (0,72] hours")
    if output.exists(): raise ValueError("Fresh follow-up output required")
    output.mkdir(parents=True)
    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    queue_hash = _sha256_file(queue_path)
    state_path = root/"runs/training"/(queue["suite_id"]+"-queue-state.json")
    references = reference_cases(reference_models, reference_ids or []) if reference_models else None
    status = {"status": "waiting_for_training", "queue_sha256": queue_hash,
              "source_commit": _git_commit(), "script_sha256": _sha256_file(Path(__file__)), "final_detector_selected": False}
    if reference_models:
        status["reference_protocol_sha256"] = _sha256_file(reference_models)
    _write_json(output/"state.json", status)
    deadline = time.monotonic()+wait_hours*3600
    try:
        while True:
            if time.monotonic() >= deadline: raise TimeoutError("Queue wait limit reached; training was not terminated")
            if state_path.is_file():
                try: state = json.loads(state_path.read_text(encoding="utf-8-sig"))
                except json.JSONDecodeError:
                    time.sleep(.1)
                    continue
                if state.get("queue_sha256") != queue_hash:
                    raise ValueError("Training queue identity changed")
                if state.get("status") == "failed": raise RuntimeError("Training queue failed; no evaluation launched")
                if state.get("status") == "passed": break
            time.sleep(15)
        if _sha256_file(queue_path) != queue_hash: raise ValueError("Queue changed during wait")
        source = Path(__file__).resolve().parents[1]
        existing = json.loads((root/"data/work/multi-model-20261104/models-val-candidates.json").read_text())
        kept = {c["id"]: c for c in existing["cases"] if c["id"] in {"custom-n-640", "coco-n-640", "rf-large-704"}}
        cases = references if references is not None else [kept[k] for k in ("custom-n-640", "coco-n-640", "rf-large-704")]
        if references is None:
            s = root/"models/pretrained/yolo26s.pt"
            cases.append({**kept["coco-n-640"], "id": "coco-s-640", "checkpoint": str(s), "checkpoint_sha256": _sha256_file(s)})
        for item in queue["queue"]:
            config = json.loads(Path(item["config"]).read_text())
            invocation = root/"runs/training"/(config["run_name"]+"-invocation.json")
            result = json.loads(invocation.read_text())
            if result.get("status") != "passed" or result.get("observed_optimizer_updates") != queue["planned_updates_each"]:
                raise ValueError("Raw model did not complete its verified update budget")
            weight = Path(result["save_dir"])/"weights/best.pt"
            cases.append({**kept["custom-n-640"], "id": item["recipe"].lower()+"-640", "checkpoint": str(weight),
                          "checkpoint_sha256": _sha256_file(weight), "training_invocation_sha256": _sha256_file(invocation)})
        suite = root/"data/work/multi-model-20261104/suite-v1/suite.json"
        env = {**os.environ, "PYTHONPATH": str(source/"src"), "YOLO_AUTOINSTALL": "false", "PYTHONUTF8": "1"}
        status["status"] = "evaluating"
        _write_json(output/"state.json", status)
        with ExitStack() as stack:
            while True:
                try:
                    stack.enter_context(gpu_training_lock(root/"runs/training/gpu0-training.lock", owner="raw-follow-up:"+queue["suite_id"]))
                    break
                except FileExistsError:
                    if time.monotonic() >= deadline: raise TimeoutError("GPU claim wait limit reached")
                    time.sleep(15)
            for track in ("ap", "predict"):
                track_root = output/track
                track_root.mkdir()
                protocol = {"schema_version": 1, "suite_sha256": _sha256_file(suite), "training_started": False,
                            "status": "frozen_development_comparison", "track": track, "cases": [],
                            "policy": {**existing["policy"], "ultralytics_candidate_convention":
                                       "per-class candidates (validator convention)" if track == "ap"
                                       else "default predict single-label candidates"}}
                for c in cases:
                    entry = dict(c)
                    if c["backend"] == "ultralytics": entry["ultralytics_multi_label"] = track == "ap"
                    protocol["cases"].append(entry)
                models = track_root/"models.json"
                _write_json(models, protocol)
                runs = track_root/"models"
                runs.mkdir()
                for case in protocol["cases"]:
                    with (track_root/(case["id"]+".log")).open("w", encoding="utf-8") as log:
                        subprocess.run([sys.executable, "-X", "utf8", str(source/"tools/run_detector_comparison.py"),
                                        "--suite", str(suite), "--models", str(models), "--case", case["id"],
                                        "--output", str(runs/case["id"]), "--authorize-development-comparison"],
                                       env=env, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
                with (track_root/"aggregate.log").open("w", encoding="utf-8") as log:
                    subprocess.run([sys.executable, "-X", "utf8", str(source/"tools/summarize_detector_comparison.py"),
                                    "--suite", str(suite), "--models", str(models), "--runs", str(runs), "--output", str(track_root/"aggregate")],
                                   env=env, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
                truth = json.loads((suite.parent/"sohas-val-truth.json").read_text())
                selection = {}
                for case in cases:
                    predictions = [json.loads(x) for x in (runs/case["id"]/"sohas-val/predictions.jsonl").read_text().splitlines()]
                    selection[case["id"]] = select_f2_operating_point(truth, predictions)
                _write_json(track_root/"tuning-f2.json", {"scope": "opened SOHAS development val23 only; provisional", "models": selection})
        status.update(status="passed", models=len(cases), tracks=["ap", "predict"], datasets=6,
                      comparison_scope="opened development images; not unseen final CCTV evaluation", final_detector_selected=False)
        rows = list(csv.DictReader((output/"ap/aggregate/comparison.csv").open(encoding="utf-8-sig")))
        text = ["# RAW 학습 후 공통 개발 평가", "",
                f"새 RAW {len(queue['queue'])}개와 기준 모델 {len(cases)-len(queue['queue'])}개를 동일한 6개 개발 자료에서 비교했다.",
                "YOLO validator 방식 AP와 실제 predict 방식은 ap/predict 폴더로 분리했다. 학습 원본은 미검수이며 이 평가는 새로운 독립 CCTV final test가 아니다.",
                "DaSCI의 기존 자료 연관성·합성 분리·소표본 한계는 원래 frozen suite와 동일하다. D* 채택이나 최종 사건 성능을 확정하지 않는다.", "",
                "| Dataset | Model | AP50 | AP50–95 | P@.25 | R@.25 | Small R@.25 | FP |", "|---|---|---:|---:|---:|---:|---:|---:|"]
        for row in rows:
            def number(key):
                return f"{float(row[key]):.4f}" if row.get(key) else "—"
            text.append("| " + " | ".join([row["dataset"], row["model"], *(number(k) for k in ("ap50", "ap50_95", "precision025", "recall025", "small_recall025")), row["fp"]]) + " |")
        text += ["", "tuning-f2.json의 threshold는 기존 SOHAS 개발 val23에서만 선택한 임시 값이다. 실제 CCTV tuning/final session으로 다시 검증해야 한다.",
                 "원시 예측·truth/checkpoint/protocol hash·group bootstrap·환경·실행 commit은 각 track의 aggregate와 model summary에 보관했다.", ""]
        (output/"report.md").write_text("\n".join(text), encoding="utf-8")
    except BaseException as exc:
        status.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output/"state.json", status)
    return status


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "queue", "output-dir"): p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--wait-hours", type=float, default=36)
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--reference-models", type=Path)
    p.add_argument("--reference-case", action="append", default=[])
    a = p.parse_args()
    readiness = preflight_environment()
    print(json.dumps(readiness), flush=True)
    if not a.preflight_only:
        print(json.dumps(finish(a.root.resolve(), a.queue.resolve(), a.output_dir.resolve(), a.wait_hours,
                               reference_models=a.reference_models, reference_ids=a.reference_case)))
