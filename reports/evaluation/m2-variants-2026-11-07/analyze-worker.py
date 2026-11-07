"""Audit completed comparison, export focused tables and standalone figures."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Class6\edge-threat-response")
SOURCE = Path(r"C:\Class6\etr-worktrees\m2-comparison-20261107")
RUN = ROOT/"runs/m2-variants-comparison-20261107-v1"
sys.path.insert(0, str(SOURCE/"src"))
from edge_threat_response.training import _sha256_file, _write_json

state = json.loads((RUN/"state.json").read_text())
if state["status"] != "passed":
    raise ValueError("Wait for both inference tracks to pass")
OUT = RUN/"analysis"
if OUT.exists():
    raise ValueError("Preserve previous analysis")
OUT.mkdir()
suite = json.loads((RUN/"suite.json").read_text())
audit = []
for track in ("predict", "ap"):
    root = RUN/track
    fixed = list(csv.DictReader((root/"aggregate/comparison.csv").open(encoding="utf-8-sig")))
    curves = list(csv.DictReader((root/"thresholds.csv").open(encoding="utf-8-sig")))
    models = json.loads((root/"models.json").read_text())
    for case in models["cases"]:
        case_root = root/"models"/case["id"]
        case_summary = json.loads((case_root/"summary.json").read_text())
        if case_summary["models_sha256"] != _sha256_file(root/"models.json"):
            raise ValueError("Model protocol identity changed")
        for name in suite["datasets"]:
            summary = case_summary["results"][name]
            prediction = case_root/name/"predictions.jsonl"
            if _sha256_file(prediction) != summary["predictions_sha256"]:
                raise ValueError("Prediction identity changed")
            row = next(r for r in fixed if r["model"] == case["id"] and r["dataset"] == name)
            point = next(r for r in curves if r["model"] == case["id"] and r["dataset"] == name
                         and float(r["confidence"]) == .25)
            if any(int(row[k]) != int(point[k]) for k in ("tp", "fp", "fn")):
                raise ValueError("Threshold .25 does not reproduce fixed counts")
            for a, b in (("precision025", "precision"), ("recall025", "recall"), ("f1_025", "f1")):
                if bool(row[a]) != bool(point[b]) or (row[a] and abs(float(row[a])-float(point[b])) > 1e-12):
                    raise ValueError("Threshold .25 does not reproduce metrics")
            # Repeated references should reproduce the earlier completed run.
            old_root = ROOT/"runs/m2-followup-20261107-v2"/track/"models"/case["id"]
            if name == "us-mock-reviewed":
                old_root = ROOT/"runs/m2-followup-20261107-v2/cctv-expanded/models"/case["id"]
            old = old_root/name/"summary.json"
            if old.exists() and not (track == "ap" and name == "us-mock-reviewed"):
                previous = json.loads(old.read_text())
                if previous["fixed"] != summary["fixed"] or abs(previous["coco"]["ap50"]-summary["coco"]["ap50"]) > 1e-12:
                    raise ValueError("Repeated baseline metrics changed")
                audit.append({"track": track, "model": case["id"], "dataset": name,
                    "fixed_metrics_identical": True, "ap50_identical": True,
                    "prediction_hash_identical": previous["predictions_sha256"] == summary["predictions_sha256"]})
    if len(fixed) != 63 or len(curves) != 693:
        raise ValueError("Missing model/dataset/threshold results")
    with (OUT/(track+"-cctv-thresholds.csv")).open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, list(curves[0])); writer.writeheader()
        writer.writerows(r for r in curves if r["dataset"] == "us-mock-reviewed")
_write_json(OUT/"verification.json", {"status": "passed", "repeated_baseline_checks": audit,
    "fixed_rows_each_track": 63, "threshold_rows_each_track": 693,
    "confidence_grid": [.001, .05, *[i/100 for i in range(10, 51, 5)]],
    "threshold025_reproduces_fixed_metrics": True,
    "final_detector_selected": False, "orin_verified": False})

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

labels = {"custom-n-640": "D0 / 640", "coco-n-640": "COCO / 640", "raw-m1-n-640": "M1 / 640",
          "raw-m2-n-640": "M2 / 640", "raw-m2-n-960": "M2 / 960",
          "pc11-infer640": "PC11 train960 / 640", "pc11-infer960": "PC11 train960 / 960",
          "pc12-infer640": "PC12 mild aug / 640", "pc14-infer640": "PC14 seed2 / 640"}
names = ["sohas-val", "sohas-test", "dasci-unique", "open-images", "simuletic", "us-mock", "us-mock-reviewed"]
short = ["SOHAS val23", "SOHAS test23", "DaSCI92", "OpenImages29", "Synthetic75", "CCTV21", "CCTV83"]
table = list(csv.DictReader((RUN/"predict/aggregate/comparison.csv").open(encoding="utf-8-sig")))
fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
for ax, key, title in zip(axes, ["ap50", "recall025"], ["AP50 (%)", "Recall at confidence .25 (%)"]):
    values = np.array([[float(next(r[key] for r in table if r["model"] == m and r["dataset"] == d))*100
                        for d in names] for m in labels])
    image = ax.imshow(values, vmin=0, vmax=100, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(names)), short, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), list(labels.values()), fontsize=8)
    ax.set_title(title)
    for y in range(len(labels)):
        for x in range(len(names)):
            ax.text(x, y, f"{values[y,x]:.1f}", ha="center", va="center", fontsize=7,
                    color="black" if values[y,x] > 60 else "white")
fig.colorbar(image, ax=axes, shrink=.7)
fig.suptitle("Predict track: opened development sets, not final evaluation\nCCTV21 overlaps CCTV83; do not pool domains", fontsize=11)
fig.savefig(OUT/"predict-comparison.png", dpi=180)
plt.close(fig)

curves = list(csv.DictReader((RUN/"predict/thresholds.csv").open(encoding="utf-8-sig")))
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
colors = plt.get_cmap("tab10")
selected = [m for m in labels if m not in {"custom-n-640", "coco-n-640"}]
for i, model in enumerate(selected):
    data = sorted([r for r in curves if r["model"] == model and r["dataset"] == "us-mock-reviewed"
                   and .1 <= float(r["confidence"]) <= .5], key=lambda r: float(r["confidence"]))
    x = [float(r["confidence"]) for r in data]
    axes[0].plot(x, [float(r["recall"])*100 for r in data], marker=".", color=colors(i), label=labels[model])
    axes[1].plot(x, [int(r["fp"]) for r in data], marker=".", color=colors(i), label=labels[model])
for ax in axes:
    ax.set_xlabel("Confidence"); ax.grid(alpha=.25)
axes[0].set_ylabel("Recall (%)"); axes[0].set_ylim(-.5, 15)
axes[1].set_ylabel("False-positive boxes")
fig.suptitle("Opened CCTV83 / 31 knife GT: confidence sweep\nFP boxes are not event false alarms", fontsize=11)
handles, legend = axes[0].get_legend_handles_labels()
fig.legend(handles, legend, loc="lower center", ncol=3, fontsize=8)
fig.tight_layout(rect=(0, .17, 1, .92))
fig.savefig(OUT/"cctv-confidence.png", dpi=180)
plt.close(fig)
_write_json(OUT/"plot-environment.json", {"matplotlib": matplotlib.__version__, "numpy": np.__version__})
print(json.dumps({"status": "passed", "baseline_checks": len(audit), "figures": 2}))
