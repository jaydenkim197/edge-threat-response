"""Measure a single GPU on synthetic YOLO26 training steps."""

import argparse
import json
import math
import os
import re
import statistics
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("yolo26n.yaml", "yolo26s.yaml", "yolo26m.yaml"),
                        default="yolo26n.yaml")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batches", type=int, nargs="+", default=[1, 4, 8, 12, 16, 24])
    parser.add_argument("--steps", type=int, default=6)
    args = parser.parse_args()
    if args.imgsz < 64 or args.imgsz % 32 or args.steps < 1 or min(args.batches) < 1:
        parser.error("Use positive batches and steps, and an image size divisible by 32.")

    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not re.fullmatch(r"GPU-(?:[0-9a-f]{8}-)(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", visible):
        parser.error("Set CUDA_VISIBLE_DEVICES to one verified physical GPU UUID.")

    import torch
    import torchvision
    import ultralytics
    from ultralytics.cfg import get_cfg
    from ultralytics.nn.tasks import DetectionModel

    if torch.cuda.device_count() != 1:
        raise RuntimeError("Expected exactly one visible CUDA GPU.")
    torch.set_num_threads(2)
    torch.manual_seed(20261126)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    box = torch.tensor([[0, 0, 2, 2]], device="cuda", dtype=torch.float32)
    if torchvision.ops.nms(box, box[:, 2], 0.5).tolist() != [0]:
        raise RuntimeError("CUDA NMS returned the wrong result.")
    print("BENCH_ENV " + json.dumps({
        "uuid": visible, "gpu": torch.cuda.get_device_name(0),
        "capability": torch.cuda.get_device_capability(0), "arch_list": torch.cuda.get_arch_list(),
        "torch": torch.__version__, "torchvision": torchvision.__version__,
        "cuda": torch.version.cuda, "ultralytics": ultralytics.__version__,
        "model": args.model, "imgsz": args.imgsz, "precision": "fp32-tf32-off", "steps": args.steps,
    }), flush=True)
    model = DetectionModel(args.model, nc=1, verbose=False).to("cuda").train()
    model.args = get_cfg()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0001)
    for batch in sorted(set(args.batches)):
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        free, total = torch.cuda.mem_get_info()
        reserved_before = torch.cuda.memory_reserved()
        try:
            sample = {
                "img": torch.rand(batch, 3, args.imgsz, args.imgsz, device="cuda"),
                "batch_idx": torch.arange(batch, device="cuda"),
                "cls": torch.zeros(batch, 1, device="cuda"),
                "bboxes": torch.tensor([0.5, 0.5, 0.12, 0.08], device="cuda").repeat(batch, 1),
            }
            samples = []
            for step in range(args.steps + 2):
                torch.cuda.synchronize()
                started = time.perf_counter()
                optimizer.zero_grad(set_to_none=True)
                loss, _ = model(sample)
                loss.sum().backward()
                optimizer.step()
                torch.cuda.synchronize()
                if not math.isfinite(loss.detach().sum().item()):
                    raise RuntimeError("Non-finite training loss.")
                if step >= 2:
                    samples.append(time.perf_counter() - started)
            peak = torch.cuda.max_memory_reserved()
            free_after, _ = torch.cuda.mem_get_info()
            minimum_headroom = min(free_after, free - max(0, peak - reserved_before))
            row = {"batch": batch, "images_per_second": batch / statistics.median(samples),
                   "step_seconds": samples, "peak_reserved_mib": peak // 2**20,
                   "total_mib": total // 2**20, "headroom_mib": minimum_headroom // 2**20,
                   "status": "pass" if minimum_headroom >= max(1024 * 2**20, int(total * 0.1))
                   else "below_headroom"}
        except torch.OutOfMemoryError:
            row = {"batch": batch, "status": "oom"}
        print("BENCH_RESULT " + json.dumps(row), flush=True)
        if row["status"] != "pass":
            break
        del sample, loss


if __name__ == "__main__":
    main()
