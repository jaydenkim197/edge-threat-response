"""Check fixed D1 deployment outputs with earlier tile candidate filtering."""

from argparse import ArgumentParser
from pathlib import Path

import cv2
import numpy as np
import torch

from edge_threat_response.p430_tile_detector import P430TiledBackend
from edge_threat_response.p430_workflow import read, require, save, sha
from p430_followup_actions import D1_SHA, PLAN_SHA, pin_plan
from run_p430_site import development_rows


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("settings", "weights", "result"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    base = Path(read(args.settings)["base"])
    require(sha(args.weights) == D1_SHA, "Expected fixed D1 weights")
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1, "Expected a reserved GPU")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    rows = development_rows(base, pin_plan(base))
    require([len(rows[split]) for split in ("tune", "dev_check")] == [298, 287], "Unexpected release size")

    threshold = .28837335109710693
    backend = P430TiledBackend(str(args.weights), predict_arguments={"device": 0, "conf": threshold})
    result = {"scope": "development_only", "base_plan_sha256": PLAN_SHA, "weights_sha256": D1_SHA,
              "post_merge": threshold, "pre_merge": [.001, .15], "splits": {}}
    for split, entries in rows.items():
        differences = []
        for item in entries:
            image = cv2.imdecode(np.frombuffer(Path(item["image_file"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            require(image is not None and image.shape == (1080, 1920, 3), "Invalid development frame")
            predictions = []
            for confidence in result["pre_merge"]:
                backend.predict_arguments["conf"] = confidence
                predictions.append(backend.predict(image))
            if predictions[0] != predictions[1]:
                differences.append({"image_sha256": item["image_sha256"],
                                    "baseline_count": len(predictions[0]), "prefilter_count": len(predictions[1])})
        result["splits"][split] = {"frames": len(entries), "different": differences}
        print(f"{split}: {len(differences)}/{len(entries)} differing frames", flush=True)
    result["same_fixed_detections"] = not any(split["different"] for split in result["splits"].values())
    save(args.result, result)


if __name__ == "__main__":
    main()
