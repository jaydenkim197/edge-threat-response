"""Read a private camera config and check bounded decode without leaking URLs."""
import argparse
import json
import time
from itertools import islice
from pathlib import Path

from edge_threat_response.media import RTSPFrameSource
from edge_threat_response.training import _write_json, _git_commit


def check(connection: Path, output: Path, max_frames: int):
    if output.exists() or max_frames < 1:
        raise ValueError("Fresh output and positive frame limit required")
    config = json.loads(connection.read_text(encoding="utf-8-sig"))
    source = RTSPFrameSource(config["rtsp_url"], source_id=config.get("source_id", "p430-pilot"))
    output.mkdir(parents=True)
    report = {"status": "running", "requested_frames": max_frames, "source_id": source.source_id,
              "source_commit": _git_commit(), "url_or_credentials_recorded": False,
              "measurement_boundary": "host decode arrival; not sensor exposure or GPIO"}
    started = time.monotonic()
    stream = iter(source)
    rows = []
    try:
        for packet in islice(stream, max_frames):
            rows.append({"frame_index": packet.frame_index, "timestamp_s": packet.timestamp_s,
                         "width": int(packet.image.shape[1]), "height": int(packet.image.shape[0])})
        report.update(status="passed", received_frames=len(rows))
    except Exception:
        report.update(status="failed", received_frames=len(rows), error="RTSP decode failed; inspect private settings locally")
        raise RuntimeError(report["error"]) from None
    finally:
        stream.close()
        report.update(wall_seconds=time.monotonic()-started, capture=dict(source.stats), frames=rows)
        _write_json(output/"probe.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--max-frames", type=int, default=120)
    a = p.parse_args()
    report = check(a.connection, a.output_dir, a.max_frames)
    print(json.dumps({k: v for k, v in report.items() if k != "frames"}))
