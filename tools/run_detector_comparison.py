"""Evaluate one frozen checkpoint on every frozen development comparison set.

Run each model in a separate process. This is an offline accuracy comparison,
not an Orin benchmark or a training entry point.
"""
import argparse
import gc
import importlib.metadata
import json
import sys
import time
from pathlib import Path

from edge_threat_response.detector_comparison import POLICY, canonical_prediction, coco_metrics
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import _environment_record, _git_commit, _sha256_file, _write_json


def load_predictor(case):
    import torch
    from PIL import Image
    if case["backend"] == "ultralytics":
        from ultralytics import YOLO
        from ultralytics.models.yolo.detect.predict import DetectionPredictor
        from ultralytics.utils import nms
        class PerClassAPPredictor(DetectionPredictor):
            """Use the official validator's multi-label candidate convention.

            Default predict results are retained as a separate comparison track.
            This changes candidate postprocessing only, not the checkpoint.
            """
            def postprocess(self, predictions, image, originals, **kwargs):
                if not isinstance(originals, list) or getattr(self.model, "end2end", False):
                    raise ValueError("Per-class AP requires RGB image inputs and the one-to-many head")
                predictions = nms.non_max_suppression(
                    predictions, self.args.conf, self.args.iou, self.args.classes,
                    self.args.agnostic_nms, multi_label=True, max_det=self.args.max_det, nc=0,
                    end2end=False, rotated=False)
                return self.construct_results(predictions, image, originals, **kwargs)
        model = YOLO(case["checkpoint"])
        knife_ids = [i for i, label in model.names.items() if label == "knife"]
        if knife_ids != [case["knife_class_id"]]:
            raise ValueError("Ultralytics knife map differs from frozen protocol")
        def predict(image):
            result = model.predict(image, device=0, imgsz=case["imgsz"], batch=1, half=False, rect=False,
                                   conf=.001, classes=[case["knife_class_id"]], iou=.7, max_det=300,
                                   nms=None, verbose=False,
                                   predictor=PerClassAPPredictor if case.get("ultralytics_multi_label") else None)[0]
            return result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()
        def provenance():
            return {"end2end": bool(model.predictor.model.end2end), "class_names": model.names,
                    "parameter_dtype": str(next(model.model.parameters()).dtype),
                    "multi_label_candidates": bool(case.get("ultralytics_multi_label")),
                    "preprocessing": "Ultralytics square letterbox; RGB input"}
        return predict, provenance
    if case["backend"] == "rfdetr":
        import rfdetr
        from rfdetr.assets.coco_classes import COCO_CLASSES
        if COCO_CLASSES[case["knife_class_id"]] != "knife":
            raise ValueError("RF-DETR sparse COCO class map mismatch")
        constructor = getattr(rfdetr, case["model_class"])
        model = constructor(pretrain_weights=case["checkpoint"], device="cuda", amp=False)
        if model.model_config.resolution != case["imgsz"]:
            raise ValueError("RF-DETR native resolution differs from protocol")
        def predict(image):
            result = model.predict(image, threshold=.001, include_source_image=False)
            return result.xyxy.tolist(), result.confidence.tolist(), result.class_id.tolist()
        def provenance():
            return {"class_names": COCO_CLASSES, "model_config": model.model_config.model_dump(mode="json"),
                    "parameter_dtype": str(next(model.model.model.parameters()).dtype),
                    "preprocessing": "official RF-DETR predict with native checkpoint preprocessing"}
        return predict, provenance
    if case["backend"] == "deimv2":
        import torch.nn as nn
        import torchvision.transforms as transforms
        from safetensors.torch import load_file
        sys.path.insert(0, case["source_dir"])
        from engine.backbone import DINOv3STAs
        from engine.deim import HybridEncoder, DEIMTransformer
        from engine.deim.postprocessor import PostProcessor
        config = json.loads(Path(case["model_config"]).read_text(encoding="utf-8"))
        class Model(nn.Module):
            def __init__(self):
                super().__init__()
                self.backbone = DINOv3STAs(**config["DINOv3STAs"])
                self.encoder = HybridEncoder(**config["HybridEncoder"])
                self.decoder = DEIMTransformer(**config["DEIMTransformer"])
                self.postprocessor = PostProcessor(**config["PostProcessor"])

            def forward(self, image, size):
                return self.postprocessor(self.decoder(self.encoder(self.backbone(image))), size)
        model = Model()
        state = load_file(case["checkpoint"])
        restored = {}
        # The official HF safetensors omits these requires_grad=False scalar
        # parameters. Restore only the two verified architecture constants; all
        # learned weights and remaining buffers must still load strictly.
        for name, value in {"decoder.up": .5, "decoder.reg_scale": float(config["DEIMTransformer"]["reg_scale"])}.items():
            if name not in state:
                parameter = model.get_parameter(name)
                if parameter.requires_grad or parameter.numel() != 1 or parameter.item() != value:
                    raise ValueError("Unexpected missing DEIMv2 architecture constant")
                state[name] = parameter.detach().clone()
                restored[name] = value
        model.load_state_dict(state, strict=True)
        model.eval().to("cuda")
        for module in [model.encoder, model.decoder, model.postprocessor]:
            if hasattr(module, "deploy"):
                module.deploy()
        preprocess = transforms.Compose([transforms.Resize((case["imgsz"], case["imgsz"])),
                                         transforms.ToTensor(),
                                         transforms.Normalize([.485, .456, .406], [.229, .224, .225])])
        if model.postprocessor.num_classes != 80 or model.postprocessor.remap_mscoco_category:
            raise ValueError("DEIMv2 must output contiguous COCO80 labels (knife43)")
        def predict(image):
            size = torch.tensor([image.size], device="cuda")
            with torch.inference_mode():
                labels, boxes, scores = model(preprocess(image).unsqueeze(0).to("cuda"), size)
            return boxes[0].tolist(), scores[0].tolist(), labels[0].tolist()
        def provenance():
            return {"model_config": config, "source_revision": case["source_revision"],
                    "parameter_dtype": str(next(model.parameters()).dtype),
                    "preprocessing": "official ViT RGB squash resize + ImageNet normalization",
                    "checkpoint_load": "safetensors strict=True after restoring verified nonlearned constants",
                    "restored_fixed_constants": restored}
        return predict, provenance
    raise ValueError("Unknown comparison backend")


def run(args):
    if not args.authorize_development_comparison:
        raise ValueError("Explicit development comparison authorization required")
    if args.output.exists():
        raise ValueError("Fresh output required")
    suite_hash, models_hash = _sha256_file(args.suite), _sha256_file(args.models)
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    models = json.loads(args.models.read_text(encoding="utf-8"))
    case = next(x for x in models["cases"] if x["id"] == args.case)
    if suite["status"] != "development_authorized" or suite["policy"] != POLICY:
        raise ValueError("Expected frozen development comparison policy")
    if _sha256_file(Path(case["checkpoint"])) != case["checkpoint_sha256"]:
        raise ValueError("Checkpoint hash changed")
    for path, digest in suite["inputs"].items():
        if _sha256_file(Path(path)) != digest:
            raise ValueError("Source changed: "+path)
    for path, digest in case.get("extra_input_sha256", {}).items():
        if _sha256_file(Path(path)) != digest:
            raise ValueError("Model configuration/source changed")
    import torch
    from PIL import Image
    if not torch.cuda.is_available():
        raise RuntimeError("PC13 CUDA required; no CPU fallback")
    torch.manual_seed(20261104)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_grad_enabled(False)
    args.output.mkdir(parents=True)
    _write_json(args.output/"started.json", {"case": case, "suite_sha256": suite_hash,
                                             "models_sha256": models_hash, "training_started": False})
    predictor, provenance = load_predictor(case)
    # Warm up on a synthetic blank, never use test results for model/config selection.
    for _ in range(3):
        predictor(Image.new("RGB", (640, 480)))
    torch.cuda.synchronize()
    results = {}
    for name, dataset in suite["datasets"].items():
        truth_path = Path(dataset["truth"])
        if _sha256_file(truth_path) != dataset["truth_sha256"]:
            raise ValueError("Truth selection changed")
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        predictions, timings, adjusted = [], [], 0
        for index, image in enumerate(truth["images"]):
            image_path = Path(image["image"])
            if _sha256_file(image_path) != image["image_sha256"]:
                raise ValueError("Image changed before inference")
            with Image.open(image_path) as original:
                if original.size != (image["width"], image["height"]) or original.getexif().get(274, 1) != 1:
                    raise ValueError("Unexpected stored-pixel geometry")
                rgb = original.convert("RGB")
            torch.cuda.synchronize()
            started = time.perf_counter()
            boxes, scores, classes = predictor(rgb)
            torch.cuda.synchronize()
            timings.append((time.perf_counter()-started)*1000)
            row, changed = canonical_prediction(image, boxes, scores, classes, case["knife_class_id"])
            predictions.append(row)
            adjusted += changed
        dest = args.output/name
        dest.mkdir()
        write_jsonl(dest/"predictions.jsonl", predictions)
        fixed, matches = evaluate_boxes(truth, predictions, POLICY)
        write_jsonl(dest/"matches.jsonl", matches)
        result = {"fixed": fixed, "coco": coco_metrics(truth, predictions),
                  "truth_sha256": dataset["truth_sha256"],
                  "predictions_sha256": _sha256_file(dest/"predictions.jsonl"),
                  "geometry_adjustment_count": adjusted,
                  "per_image_api_ms_PC13_not_Orin_benchmark": timings}
        _write_json(dest/"summary.json", result)
        results[name] = result
        print(json.dumps({"case": args.case, "dataset": name, "completed_images": len(predictions),
                          "ap50": result["coco"]["ap50"], "recall025": fixed["recall"]}), flush=True)
    for path, digest in suite["inputs"].items():
        if _sha256_file(Path(path)) != digest:
            raise ValueError("Source changed during evaluation")
    if (_sha256_file(args.suite) != suite_hash or _sha256_file(args.models) != models_hash
            or _sha256_file(Path(case["checkpoint"])) != case["checkpoint_sha256"]):
        raise ValueError("Frozen experiment input changed")
    packages = {x: importlib.metadata.version(x) for x in ["rfdetr", "pycocotools", "safetensors", "transformers", "timm"]}
    _write_json(args.output/"summary.json", {"status": "completed_development_comparison", "case": case,
                                             "suite_sha256": suite_hash, "models_sha256": models_hash,
                                             "script_sha256": _sha256_file(Path(__file__)), "git_commit": _git_commit(),
                                             "training_started": False, "environment": _environment_record(),
                                             "extra_packages": packages, "effective_model": provenance(),
                                             "cuda_device": torch.cuda.get_device_name(0), "results": results})
    del predictor
    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ["suite", "models", "output"]:
        parser.add_argument("--"+flag, type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--authorize-development-comparison", action="store_true")
    run(parser.parse_args())
