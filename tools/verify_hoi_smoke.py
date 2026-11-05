"""CPU wiring verification on synthetic data; not model accuracy evidence."""
import argparse
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.domain import AblationMode
from edge_threat_response.hoi import train, load_pairs, TorchRelationProvider, predict_rows, export_scores
from edge_threat_response.detector import CallableBackend, MappedDetector, RawDetection
from edge_threat_response.media import OpenCVFrameSource
from edge_threat_response.replay_cli import main as replay_main
from edge_threat_response.runtime import run_detection_stream, run_live_pipeline
from edge_threat_response.training import _sha256_file, _write_json, _git_commit, _environment_record


def verify(output: Path, inference_device="cpu"):
    from edge_threat_response.jetson_memory import prepare_jetson_memory
    memory_policy = prepare_jetson_memory()
    import cv2
    import numpy as np
    if output.exists(): raise ValueError("Fresh smoke output required")
    output.mkdir(parents=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tests"))
    from test_hoi import synthetic_pairs
    pairs, _ = synthetic_pairs(output)
    rows = load_pairs(pairs, output)
    results = {}
    for kind in ("G", "VG"):
        config = {"schema_version": 1, "kind": kind, "crop_size": 224, "data_kind": "synthetic", "pretrained": False,
                  "device": "cpu", "batch": 4, "epochs": 1, "early_stopping_patience": 2, "seed": 20261004}
        path = output/f"{kind}.json"
        _write_json(path, config)
        run = output/kind
        result = train(path, pairs, output, run)
        a, b = TorchRelationProvider(run/"best.pt", device=inference_device), TorchRelationProvider(run/"best.pt", device=inference_device)
        scores = predict_rows(a.model, rows, kind=kind, size=224, device=inference_device)
        reloaded = predict_rows(b.model, rows, kind=kind, size=224, device=inference_device)
        if scores != reloaded or not all(0 <= x <= 1 for x in scores):
            raise RuntimeError("Checkpoint reload predictions changed")
        results[kind] = {"status": result["status"], "checkpoint_sha256": a.checkpoint_sha256,
                         "reload_identical": True, "duration_seconds": result["duration_seconds"]}
    media = output/"synthetic.avi"
    writer = cv2.VideoWriter(str(media), cv2.VideoWriter_fourcc(*"MJPG"), 10., (48, 48))
    if not writer.isOpened(): raise RuntimeError("Synthetic video writer unavailable")
    for i in range(4): writer.write(np.full((48, 48, 3), 30+i*20, dtype=np.uint8))
    writer.release()
    detector = MappedDetector("synthetic-only", CallableBackend(lambda image: (
        RawDetection(0, .99, (2, 2, 30, 46)), RawDetection(1, .99, (24, 20, 29, 30)))), {0: "person", 1: "knife"})
    detection_dir = output/"detect"
    run_detection_stream(OpenCVFrameSource(media, source_id="synthetic-hoi"), detector, output_dir=detection_dir,
                         provenance={"input": {"sha256": _sha256_file(media)}, "data_kind": "synthetic"})
    cfg = Path(__file__).resolve().parents[1]/"configs/replay/development-v2.example.json"
    sidecar = output/"relations.jsonl"
    score_result = export_scores(output/"VG/best.pt", detection_dir/"detections.jsonl", media, cfg, sidecar, inference_device)
    with redirect_stdout(StringIO()):
        replay_main(["--input", str(detection_dir/"detections.jsonl"), "--config", str(cfg), "--output-dir", str(output/"replay"),
                     "--modes", "B0,B1,B2,B3,B4", "--relations", str(sidecar), "--relation-threshold", "0"])
    provider = TorchRelationProvider(output/"VG/best.pt", device=inference_device)
    live = run_live_pipeline(OpenCVFrameSource(media, source_id="synthetic-hoi"), detector,
                             load_pipeline_config(cfg).for_mode(AblationMode.B4), output_dir=output/"live",
                             relation=provider, relation_threshold=0.)
    if live["frame_count"] != 4 or live["event_count"] != 1 or live["snapshot_count"] != 1:
        raise RuntimeError("B4 video/snapshot wiring failed")
    report = {"data_kind": "synthetic_only", "status": "passed", "git_commit": _git_commit(),
              "environment": _environment_record(),
              "native_memory_policy": memory_policy,
              "source_sha256": {name: _sha256_file(Path(__file__).resolve().parents[1]/name) for name in (
                  "src/edge_threat_response/hoi.py", "src/edge_threat_response/relations.py", "src/edge_threat_response/pipeline.py",
                  "src/edge_threat_response/runtime.py", "src/edge_threat_response/replay_cli.py", "tools/verify_hoi_smoke.py")},
              "models": results, "score_export": score_result, "live_frames": live["frame_count"],
              "live_events": live["event_count"], "live_snapshots": live["snapshot_count"],
              "forced_wiring_threshold": 0., "accuracy_claim": False,
              "camera_gpio_verified": False, "pretrained_visual_weights_tested": False,
              "inference_device": inference_device, "target_cuda_inference_verified": inference_device.startswith("cuda")}
    _write_json(output/"verification.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--inference-device", default="cpu")
    args = parser.parse_args()
    print(json.dumps(verify(args.output_dir, args.inference_device), ensure_ascii=False))
