"""Render publication-exportable figures from aggregate metrics only."""
import argparse
import json
from pathlib import Path


def plot(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    if aggregate["status"] != "completed_development_comparison":
        raise ValueError("Complete comparison required")
    if args.output.exists():
        raise ValueError("Use a fresh figure directory")
    columns = ["sohas-val", "sohas-test", "us-mock", "open-images", "dasci-unique", "simuletic"]
    names = ["custom-n-640", "coco-n-640", "coco-m-640", "coco-l-640", "coco-x-640",
             "rf-small-512", "rf-medium-576", "rf-large-704", "deimv2-s-640"]
    labels = ["Fine-tuned YOLO26n", "Pretrained YOLO26n", "Pretrained YOLO26m", "Pretrained YOLO26l",
              "Pretrained YOLO26x", "RF-DETR Small", "RF-DETR Medium", "RF-DETR Large", "DEIMv2-S"]
    short = ["SOHAS val\n(tuning)", "SOHAS test\n(opened dev)", "US Mock\n(real CCTV)",
             "Open Images\n(web images)", "DaSCI\n(related source)", "Simuletic\n(synthetic)"]
    data = aggregate["datasets"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none", "pdf.fonttype": 42,
                         "svg.hashsalt": "etr-20261104"})
    fig, axes = plt.subplots(1, 2, figsize=(16.5, 7.0), layout="constrained")
    for ax, metric, title in zip(axes, ["ap", "recall"], ["Knife AP50 (%)", "Small-knife recall at confidence 0.25 (%)"]):
        values = []
        for name in names:
            row = []
            for col in columns:
                value = (data[col]["models"][name]["coco"]["ap50"] if metric == "ap"
                         else data[col]["models"][name]["fixed"]["small_box_recall"])
                row.append(100*value if value is not None else float("nan"))
            values.append(row)
        im = ax.imshow(np.array(values), cmap="Blues", vmin=0, vmax=100, aspect="auto")
        ax.set_title(title, fontsize=12, pad=12)
        ax.set_xticks(range(len(columns)), short, fontsize=9)
        ax.set_yticks(range(len(names)), labels, fontsize=10)
        for i, row in enumerate(values):
            for j, value in enumerate(row):
                ax.text(j, i, f"{value:.1f}" if np.isfinite(value) else "N/A", ha="center", va="center", fontsize=9,
                        color="white" if value > 58 else "#152539")
        ax.axhline(.5, color="#e39029", linewidth=2)
        ax.axvline(3.5, color="#c4c4c4", linewidth=1)
        ax.axvline(4.5, color="#c4c4c4", linewidth=1)
        fig.colorbar(im, ax=ax, fraction=.035, pad=.025, ticks=[0, 25, 50, 75, 100])
    track = aggregate.get("protocol", {}).get("ultralytics_candidate_convention", "default predict")
    fig.suptitle("Pretrained vs fine-tuned detectors | "+track, fontsize=15)
    totals = " | ".join(f"{col}: {data[col]['images']} images / {data[col]['knife_objects']} knives" for col in columns)
    fig.supxlabel(totals+"\nSame images/labels and common COCO evaluator; native model input sizes. No Orin speed or final-test claim.", fontsize=8)
    args.output.mkdir(parents=True)
    for suffix in ["png", "svg", "pdf"]:
        fig.savefig(args.output/("detector-comparison."+suffix), dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    plot(parser.parse_args())
