"""Profile train-only camera conditions or train one P430 source-held-out arm."""

from argparse import ArgumentParser
from collections import defaultdict
import os
from pathlib import Path
import shutil
from statistics import median

from edge_threat_response.p430_workflow import MODEL_SHA, now, read, require, save, sha
from p430_followup_actions import PLAN_SHA, pin_plan, site_receipt
from run_p430_integration import paths
from run_p430_site import BUDGET, development_rows, draw_parents, execute, input_paths, original_boxes
import run_p430_site


def profile(base, plan, evidence):
    import cv2
    import numpy as np

    groups = defaultdict(list)
    for key, row in sorted(plan["pool"].items()):
        if row["domain"] == "p430":
            groups[row["session"]].append((key, row))
    report = {}
    for session, items in sorted(groups.items()):
        rows = []
        for key, row in items[::max(1, len(items) // 96)][:96]:
            image, label = paths(base, row)
            require(sha(image) == key and sha(label) == row["label_sha256"], "Profile inputs changed")
            pixels = cv2.imdecode(np.frombuffer(image.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            require(pixels is not None and pixels.shape == (1080, 1920), "Unexpected camera input")
            gray = cv2.resize(pixels, (960, 540), interpolation=cv2.INTER_AREA)
            labels = original_boxes(label)
            rows.append({"brightness": float(np.median(gray)), "contrast": float(gray.std()),
                         "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_32F).var()),
                         "dark_fraction": float((gray <= 16).mean()), "bright_fraction": float((gray >= 240).mean()),
                         "short_side": min((min(w * 960, h * 540) for _, _, w, h in labels), default=None)})
        report[session] = {"train_parents": len(items), "sampled": len(rows),
                           "medians": {name: median(values) if (values := [r[name] for r in rows if r[name] is not None])
                                       else None for name in rows[0]}}
    save(evidence, {"scope": "development_train_only", "base_plan_sha256": PLAN_SHA,
                    "recordings": report, "at": now(),
                    "limits": "Image-domain proxies; scene content differs and no codec cause is inferred."})


def prepare_run(base, plan, settings, tag, transform=False, coco=False):
    node = settings["trainer_node"]
    work = base.parent / f"overnight-{tag}-{node}-20261127-v1"
    work.mkdir(exist_ok=False)
    shutil.copy2(base / "protection.json", work / "protection.json")
    used = {(key, view) for epoch in plan["draws"] for key, view in epoch}
    for key, tiled in sorted(used):
        if not tiled:
            continue
        originals = input_paths(base, plan, key, True)
        # Site training verifies every pair and regenerates missing pairs from the pinned parent.
        if not all(path.is_file() for path in originals):
            continue
        for origin, target in zip(originals, input_paths(work, plan, key, True), strict=True):
            target.parent.mkdir(exist_ok=True, parents=True)
            try:
                os.link(origin, target)
            except OSError:
                shutil.copyfile(origin, target)
    spec = {"budget": BUDGET}
    if transform:
        from PIL import Image, ImageEnhance

        views = []
        for key, tiled in sorted(used):
            if plan["pool"][key]["domain"] != "cctv":
                continue
            original, original_label = input_paths(base, plan, key, tiled)
            meta = plan["tiles"][key] if tiled else plan["pool"][key]
            require(sha(original) == (meta["image_sha256"] if tiled else key)
                    and sha(original_label) == meta["label_sha256"], "External CCTV pair changed")
            name = key + ("-tile" if tiled else "-full") + ".png"
            image, label = work / "views/images" / name, work / "views/labels" / (Path(name).stem + ".txt")
            image.parent.mkdir(exist_ok=True, parents=True)
            label.parent.mkdir(exist_ok=True, parents=True)
            with Image.open(original) as pixels:
                ImageEnhance.Contrast(pixels.convert("RGB")).enhance(.8).save(image)
            shutil.copyfile(original_label, label)
            views.append({"parent": key, "tiled": tiled, "image": name, "sha256": sha(image)})
        require(views, "No external CCTV training input available")
        save(work / "training-views.json", views)
        spec["training_views_sha256"] = sha(work / "training-views.json")
    save(work / "plan.json", plan)
    release = {"variant": "followup", "seed": 3407, "plan_sha256": sha(work / "plan.json"),
         "protection_sha256": sha(work / "protection.json"), "runner_sha256": sha(Path(run_p430_site.__file__)),
         "experiment": spec}
    if coco:
        weight = settings["weights"]["yolo26n.pt"]
        initial = Path(weight["path"])
        require(sha(initial) == weight["sha256"], "COCO YOLO26n initialization differs")
        shutil.copyfile(initial, work / "yolo26n.pt")
        release.update(variant="coco", model="yolo26n.pt", initial_sha256=weight["sha256"])
    save(work / "release.json", release)
    return work, node


def cross(base, plan, settings, train_session, evidence):
    require(sha(base.parent / "p430-t1-20261120-v1" / "initial.pt") == MODEL_SHA,
            "Expected the pre-site D0 initializer")
    groups = {row["source_group"] for row in plan["pool"].values()
              if row["domain"] == "p430" and row["session"] == train_session}
    require(len(groups) == 1, "Expected a unique P430 source group for the training recording")
    train_group = next(iter(groups))
    validation_rows = development_rows(base, plan)
    tuning = [row["image_sha256"] for row in validation_rows["tune"] if row["source_video_sha256"] == train_group]
    check = [row["image_sha256"] for row in validation_rows["dev_check"] if row["source_video_sha256"] != train_group]
    held = {row["source_video_sha256"] for row in validation_rows["dev_check"] if row["image_sha256"] in check}
    require(tuning and check and len(held) == 1 and train_group not in held, "Unclear held-out recording")
    plan["pool"] = {key: row for key, row in plan["pool"].items() if row["source_group"] not in held
                    and (row["domain"] != "p430" or row["source_group"] == train_group)}
    plan["tiles"] = {key: tile for key, tile in plan["tiles"].items() if key in plan["pool"]}
    plan["validation"] = {"tune": tuning, "dev_check": check}
    sources = defaultdict(list)
    for row in plan["pool"].values():
        sources[row["domain"]].append(row)
    plan["draws"] = draw_parents(sources, plan["tiles"], BUDGET)
    plan["summary"]["parent_plan_sha256"] = PLAN_SHA
    work, node = prepare_run(base, plan, settings, f"session-cross-{train_session}-r1")
    save(evidence.parent / "work.json", {"path": str(work), "plan_sha256": sha(work / "plan.json"),
                                         "source_holdout": sorted(held), "tune": len(tuning), "check": len(check)})
    execute(work, node)
    save(evidence, {**site_receipt(work / f"{work.name}-{node}"), "train_session": train_session,
                    "held_out": len(check), "tune": len(tuning), "initial_sha256": MODEL_SHA})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    parser.add_argument("evidence", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--train-session", type=int, choices=(1, 2))
    mode.add_argument("--degradation", choices=("control", "contrast"))
    mode.add_argument("--rf-control", action="store_true")
    args = parser.parse_args()
    settings = read(args.settings)
    base = Path(settings["base"])
    plan = pin_plan(base)
    if args.rf_control:
        plan["draws"] = [plan["draws"][0]] * len(plan["draws"])
        work, node = prepare_run(base, plan, settings, "alt04-yolo-control", coco=True)
        save(args.evidence.parent / "work.json", {"path": str(work), "plan_sha256": sha(work / "plan.json")})
        execute(work, node)
        save(args.evidence, {**site_receipt(work / f"{work.name}-{node}"), "scope": "development_only",
             "deck": "epoch-1 of pinned plan repeated each epoch", "initial_sha256": read(work / "release.json")["initial_sha256"]})
    elif args.degradation:
        work, node = prepare_run(base, plan, settings, f"alt05-{args.degradation}",
                                 transform=args.degradation=="contrast")
        save(args.evidence.parent / "work.json", {"path": str(work), "plan_sha256": sha(work / "plan.json")})
        execute(work, node)
        save(args.evidence, {**site_receipt(work / f"{work.name}-{node}"), "degradation": args.degradation,
                            "initial_sha256": MODEL_SHA})
    elif args.train_session is None:
        profile(base, plan, args.evidence)
    else:
        cross(base, plan, settings, args.train_session, args.evidence)
