"""Prepare and run paired, source-balanced P430 detector development experiments."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.p430_evaluation import evaluate_checkpoint, make_truth, rank_key
from edge_threat_response.p430_queue import candidate_metrics, process_lock
from edge_threat_response.p430_workflow import EXTERNAL_SHA, MODEL_SHA, SOURCE_SHA, now, read, require, save, sha
from edge_threat_response.training import gpu_training_lock, run_training

SCHEDULE = {"pc11": (1, ("balanced", "hardneg", "size640")),
            "pc12": (1, ("natural", "small", "exposure")),
            "pc13": (2, ("balanced", "hardneg", "size640")),
            "pc14": (2, ("natural", "small", "exposure"))}
EPOCHS = 6
DRAWS = 16384
M2_SHA = "120a05f7eb48da60ca70bbc2c0fb67a3320ea52ab60a39c55c5af37fcf311f56"
SUITE_SHA = "258caf410b16887fe4aedc55366871eff65faed183a143642e308b59eef33bae"
CCTV_SHA = "d15dcbafa822b2f4d3cbd7ef1abcd7f7f48440439e8e481d6af076bb59534a61"


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]


def paths(work, row):
    root = work.parent.parent
    processed = root / "data/processed"
    reviewed = processed / "s1-video-reviewed-20261114-v1"
    folders = {"m2": processed / "m2-real-20261107-v1",
               "cctv": reviewed if (reviewed / "added-manifest.jsonl").is_file() else processed / "cctv-only-20261114-v1",
               "p430": work.parent / "p430-t1-20261120-v1/dataset"}
    directory = folders[row["domain"]]
    return directory / "images" / row["image"], directory / "labels" / row["label"]


def packed(row, domain, *, p430=False):
    return {"image": Path(row["image"]).name, "label": Path(row.get("label", Path(row["image"]).with_suffix(".txt"))).name,
            "image_sha256": row["image_sha256"], "label_sha256": row["label_sha256"], "domain": domain,
            "source_group": row["source_video_sha256"] if p430 else row["source_group"],
            "group": str(int(row["timestamp_s"] // 10)) if p430 else row["source_group"],
            "n": row["knife_boxes"] if p430 else row["knife_count"],
            **({"session": int(row["session"][-2:])} if p430 else {})}


def pixel_short_side(label, signature, count):
    result = []
    w, h = signature["width"], signature["height"]
    for line in label.read_text(encoding="utf-8").splitlines():
        cid, x, y, bw, bh = map(float, line.split())
        require(cid == 0 and -1e-6 <= x-bw/2 < x+bw/2 <= 1+1e-6
                and -1e-6 <= y-bh/2 < y+bh/2 <= 1+1e-6, "Invalid knife box")
        result.append(min(bw*w, bh*h)*960/max(w,h))
    require(len(result) == count, "Manifest knife count differs from YOLO label")
    return min(result, default=1e9)


def signature(work, row):
    image, label = paths(work, row)
    require(sha(label) == row["label_sha256"], "Changed label: " + label.name)
    item = image_signature(image, expected_sha256=row["image_sha256"])
    return {**row, **item, "small": pixel_short_side(label, item, row["n"]) < 16}


def close_groups(rows, references):
    # Restrict this cross-source screen to comparable aspect ratios.
    source = [(int(r["dhash64"], 16), r["width"]/r["height"], r["source_group"])
              for r in rows if not r["low_information"]]
    result = set()
    for row in references:
        if row["low_information"]:
            continue
        bits, ratio = int(row["dhash64"], 16), row["width"]/row["height"]
        result.update(group for a, ar, group in source if (a ^ bits).bit_count() <= 4 and .9 <= ar/ratio <= 1.1)
    return result


def repeated(rows, total, rng):
    if total <= 0:
        return []
    require(rows, "Missing sample category")
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)
    for values in groups.values():
        rng.shuffle(values)
    group_order = sorted(groups)
    rng.shuffle(group_order)
    positions = Counter()
    sampled = []
    while len(sampled) < total:
        for group in group_order:
            queue = groups[group]
            sampled.append(queue[positions[group] % len(queue)])
            positions[group] += 1
            if len(sampled) == total:
                break
    return sampled


def extras(pool, total, variant, rng):
    pos = [r for r in pool if r["n"]]
    neg = [r for r in pool if not r["n"]]
    positives = round(total*len(pos)/len(pool))
    pos_rng = random.Random(rng.getrandbits(64))
    neg_rng = random.Random(rng.getrandbits(64))
    positive_repeat = repeated(pos, positives, pos_rng)
    if variant == "small" and any(r["small"] for r in pos):
        small = [r for r in pos if r["small"]]
        ordinary = [r for r in pos if not r["small"]]
        count = min(positives, max(sum(r["small"] for r in positive_repeat), round(.75*positives)))
        if ordinary:
            positive_repeat = repeated(small, count, pos_rng) + repeated(ordinary, positives-count, pos_rng)
    negative_repeat = repeated(neg, total-positives, neg_rng)
    if variant == "hardneg":
        hard = [r for r in neg if r["hard_score"] >= .025]
        if hard:
            count = len(negative_repeat)//2
            negative_repeat = repeated(hard, count, neg_rng) + repeated(neg, len(negative_repeat)-count, neg_rng)
    return positive_repeat + negative_repeat


def prepare(work):
    root = work.parent.parent
    m2 = root / "data/processed/m2-real-20261107-v1/inventory.jsonl"
    s1 = root / "data/processed/s1-video-reviewed-20261114-v1/added-manifest.jsonl"
    external_path = work.parent / "s1-adapt-20261115-v1/plan.json"
    base = work.parent / "p430-t1-20261120-v1"
    capture = base / "dataset/manifest.jsonl"
    suite = work.parent / "s1-comparison-20261108-v1/suite.json"
    inputs = {m2: M2_SHA, s1: CCTV_SHA, external_path: EXTERNAL_SHA, capture: SOURCE_SHA, suite: SUITE_SHA}
    require(all(sha(path) == digest for path, digest in inputs.items()), "Protected input manifest hash mismatch")
    mixed_model = root / "runs/training/s1-video-reviewed-20261114-v1/weights/best.pt"
    require(sha(mixed_model) == sha(base / "initial.pt") == MODEL_SHA, "Initialization differs from the prior mixed model")
    m2_rows = jsonl(m2)
    external = read(external_path)
    old_tune = external["tune"]
    held_groups = {r["source_group"] for r in old_tune} | {r["source_group"] for r in m2_rows if r["split"] != "train"}
    held_hashes = {r["image_sha256"] for r in old_tune} | {r["image_sha256"] for r in m2_rows if r["split"] != "train"}
    prior_truth = {}
    for definition in read(suite)["datasets"].values():
        path = Path(definition["truth"])
        require(sha(path) == definition["truth_sha256"], "Prior development truth changed")
        for row in read(path)["images"]:
            held_hashes.add(row["image_sha256"])
            if row.get("source_group"):
                held_groups.add(row["source_group"])
            prior_truth[row["image_sha256"]] = Path(row["image"])
    authorized = {r["image_sha256"]: r for r in external["pos"] + external["neg_pool"]}
    reviewed = jsonl(s1)
    held_cctv_hashes = {r["image_sha256"] for r in old_tune}
    held_videos = {r["video_sha256"] for r in reviewed if r["image_sha256"] in held_cctv_hashes}
    cctv = []
    for reviewed_row in reviewed:
        candidate = authorized.get(reviewed_row["image_sha256"])
        if not candidate:
            continue
        require(reviewed_row["label_sha256"] == candidate["label_sha256"]
                and reviewed_row["knife_count"] == candidate["knife_count"]
                and reviewed_row["source_group"] == reviewed_row["video_sha256"]
                and reviewed_row["video_sha256"] not in held_videos,
                "CCTV trace does not match reviewed development pool")
        cctv.append(packed({**reviewed_row, "source_group": candidate["source_group"]}, "cctv"))
    general = [packed(r, "m2") for r in m2_rows if r["split"] == "train"]
    local = [packed(r, "p430", p430=True) for r in jsonl(capture)]
    require(len(general) == 11884 and len(cctv) == len(authorized) and len(local) == 1901, "Missing audited candidates")
    require(not ({r["source_group"] for r in general+cctv} & held_groups)
            and not ({r["image_sha256"] for r in general+cctv} & held_hashes), "Prior protected data crosses training")
    require(len({r["image_sha256"] for r in general+cctv+local}) == len(general+cctv+local), "Exact cross-source duplicate")
    require(not ({r["image_sha256"] for r in local} & held_hashes), "Local capture exact match in other holdout")
    print("verified roots and lineage", len(general), len(cctv), len(local), flush=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        audited = list(executor.map(lambda row: signature(work, row), general+cctv+local))
        protected_images = {r["image_sha256"]: Path(r["image"]) for r in m2_rows if r["split"] != "train"}
        protected_images.update(prior_truth)
        protected_images.update({r["image_sha256"]: root/"data/processed/s1-video-reviewed-20261114-v1/images"/Path(r["image"]).name
                                 for r in old_tune})
        holdout = list(executor.map(lambda item: {**image_signature(item[1], expected_sha256=item[0]), "source_group": item[0]},
                                    protected_images.items()))
    print("audited images, labels and protected images", len(audited), len(holdout), flush=True)
    general = [r for r in audited if r["domain"] == "m2"]
    cctv = [r for r in audited if r["domain"] == "cctv"]
    local = [r for r in audited if r["domain"] == "p430"]
    general_cross = close_groups(general+cctv, local)
    common = [r for r in general+cctv if r["source_group"] not in general_cross]
    local_cross = close_groups(local, holdout)
    hard_path = work / "external-hard.json"
    hard = {r["image_sha256"]: r["score"] for r in read(hard_path)["scores"]}
    for name, digest in ((base/"evaluation/initial.jsonl", "a5e568d95c4c3b9c64db010f826fd31fe70c9e207850a6674f86444dc988c848"),
                         (work/"p430-session-02-baseline.jsonl", "30a76b76c21d3c5b47f5b2e7de8d7d66035dd6051aed6f9078fda0cb5a7a7172")):
        require(sha(name) == digest, "Hard-negative detector predictions changed")
        hard.update({p["source_id"]: max((m["confidence"] for m in p["detections"]), default=0.) for p in jsonl(name)})
    for row in common+local:
        row["hard_score"] = hard.get(row["image_sha256"], 0.)
    summary = {"common_before_screen": dict(Counter(r["domain"] for r in general+cctv)),
               "common_after_screen": dict(Counter(r["domain"] for r in common)),
               "cross_source_excluded": len(general+cctv)-len(common),
               "capture_groups_matching_prior_holdout": len(local_cross),
               "protected_images": len(holdout), "draws": DRAWS, "epochs": EPOCHS, "folds": {}}
    for fold in (1, 2):
        p430 = [r for r in local if r["session"] == fold]
        # P430 recording groups are never split.
        require(not ({r["source_group"] for r in p430} & local_cross), "P430 source matched prior holdout dHash")
        require(len({r["source_group"] for r in local}) == 2, "Expected two distinct P430 recordings")
        val = [r for r in local if r["session"] != fold]
        summary["folds"][str(fold)] = build_fold(work, fold, common, p430, val)
    save(work/"audit.json", summary)
    print(json.dumps(summary), flush=True)

def build_fold(work, fold, common, p430, val):
    pool = common+p430
    sources = {domain: [r for r in pool if r["domain"] == domain] for domain in ("m2","cctv","p430")}
    targets = {"m2": DRAWS-1668-2832, "cctv": 1668, "p430": 2832}
    require(all(len(records) <= targets[domain] for domain, records in sources.items()), "Train target cannot cover entire pool")
    by_hash = {r["image_sha256"]: r for r in pool}
    configs = {}
    for variant in ("natural", "balanced", "small", "hardneg", "size640", "exposure"):
        rng = random.Random(3407+fold)
        if variant == "natural":
            remaining = DRAWS-len(pool)
            counts = {k: len(sources[k])+round(remaining*len(sources[k])/len(pool)) for k in targets}
            counts["m2"] += DRAWS-sum(counts.values())
        else:
            counts = targets
        selected = list(pool)
        for domain, records in sources.items():
            selected.extend(extras(records, counts[domain]-len(records),
                                   "balanced" if domain == "m2" else variant, rng))
        require(len(selected) == DRAWS, "Incorrect draw count")
        rng.shuffle(selected)
        configs[variant] = dict(draws=[r["image_sha256"] for r in selected],
                                counts=dict(Counter(r["domain"] for r in selected)),
                                positive=sum(bool(r["n"]) for r in selected),
                                small=sum(r["small"] for r in selected),
                                hard_negative=sum(not r["n"] and r["hard_score"]>=.025 for r in selected))
    save(work/f"fold-{fold}.json", dict(training=by_hash, validation={r["image_sha256"]:r for r in val}, configs=configs))
    return dict(unique=len(pool), validation=len(val),
                                      conditions={k:{x:y for x,y in v.items() if x!="draws"} for k,v in configs.items()})


def node_input(work, node):
    fold, variants = SCHEDULE[node]
    local = read(work / "local.json")
    plan_path = work / f"fold-{fold}.json"
    require(sha(plan_path) == local["plan_sha256"], "Fold plan hash mismatch")
    require(sha(Path(__file__).resolve()) == local["runner_sha256"], "Runner hash mismatch")
    plan = read(plan_path)
    prior = work.parent / "p430-t1-20261120-v1"
    old_val = prior / "config/val-manifest.json"
    require(sha(old_val) == local["val_manifest_sha256"], "Prior validation manifest changed")
    val = read(old_val)
    require(set(plan["validation"]) == {r["image_sha256"] for r in val}, "Validation does not match older runs")
    require(not (plan["training"].keys() & plan["validation"].keys()), "Training/validation image overlap")
    for manifest_row in val:
        required = plan["validation"][manifest_row["image_sha256"]]
        image, label = paths(work, required)
        require(Path(manifest_row["image_file"]) == image and Path(manifest_row["annotation_file"]) == label
                and manifest_row["label_sha256"] == required["label_sha256"], "Validation identity changed")
    for row in list(plan["training"].values())+list(plan["validation"].values()):
        image, label = paths(work, row)
        require(sha(image) == row["image_sha256"] and sha(label) == row["label_sha256"], "Missing or changed input: " + image.name)
    baseline = read(prior/"evaluation/summary.json")["baseline"]
    require(sha(prior/"initial.pt") == baseline["checkpoint_sha256"] == MODEL_SHA
            and sha(prior/"evaluation/initial.jsonl") == baseline["predictions_sha256"]
            and make_truth(val) == read(prior/"evaluation/ground-truth.json"), "Previous baseline identity changed")
    baseline.update(total_positive=sum(bool(r["boxes"]) for r in val), negative_frames=sum(not r["boxes"] for r in val))
    return local, plan, val, baseline, variants


def train_variant(work, node, variant, run):
    import torch
    from ultralytics import YOLO, __version__

    require(torch.cuda.is_available() and "RTX 3060" in torch.cuda.get_device_name(0)
            and __version__ == "8.4.152", "Expected pinned CUDA / Ultralytics environment")
    local, plan, val, baseline, variants = node_input(work, node)
    require(variant in variants, "Unassigned variant")
    prior = work.parent / "p430-t1-20261120-v1"
    sys.path.insert(0, str(prior/"evaluation-deps"))
    train = [paths(work, plan["training"][key])[0] for key in plan["configs"][variant]["draws"]]
    validation = [Path(row["image_file"]) for row in val]
    require(len(train) == DRAWS and set(train).isdisjoint(validation), "Unexpected training list")
    for section, rows in (("train", train), ("val", validation)):
        (run/(section+".txt")).write_text("".join(row.as_posix()+"\n" for row in rows), encoding="utf-8")
    data = run/"data.yaml"
    data.write_text(f"path: {run.as_posix()}\ntrain: train.txt\nval: val.txt\nnames:\n  0: knife\n", encoding="utf-8")
    args = read(prior/"config.json")["args"]
    args.update(epochs=EPOCHS, imgsz=640 if variant=="size640" else 960, lr0=.0001, save_period=1)
    if variant == "exposure":
        args.update(hsv_s=.23, hsv_v=.30)
    profile = run/"profile.json"
    save(profile, dict(schema_version=1, profile_id=variant, model=str(prior/"initial.pt"),
                       task="detect", run_name="train", arguments=args))
    evidence = {"git_commit": local["git_commit"], "gpu": torch.cuda.get_device_name(0), "started_at": now(),
                "run_id": run.name, "variant": variant, "profile_sha256": sha(profile), "plan_sha256": local["plan_sha256"],
                "initial_sha256": MODEL_SHA, "train_list_sha256": sha(run/"train.txt"), "val_list_sha256": sha(run/"val.txt")}
    save(run/"run.json", evidence)
    expected_train, expected_val = Counter(train), Counter(validation)

    def factory(checkpoint):
        model = YOLO(checkpoint)
        require(model.names == {0:"knife"}, "Unexpected detector labels")

        def loader(trainer):
            require(Counter(map(Path, trainer.train_loader.dataset.im_files)) == expected_train
                    and Counter(map(Path, trainer.test_loader.dataset.im_files)) == expected_val,
                    "Actual loader differs from the audited split or draw counts")
            save(run/"progress.json", dict(phase="training", epoch=0, epochs=EPOCHS, batches=len(trainer.train_loader), at=now()))

        model.add_callback("on_train_start", loader)
        model.add_callback("on_fit_epoch_end", lambda trainer: save(
            run/"progress.json", dict(phase="training", epoch=trainer.epoch+1, epochs=EPOCHS, at=now())))
        return model

    run_training(profile, data_yaml=data, output_dir=run, model_factory=factory,
                 dataset_manifest=work/f"fold-{SCHEDULE[node][0]}.json")
    with (run/"train/results.csv").open(newline="", encoding="utf-8") as stream:
        require(len(list(csv.DictReader(stream))) == EPOCHS, "Number of trained epochs differs")
    weights = run/"train/weights"
    candidates, seen = [], set()
    for name in ("best.pt", "last.pt", *(f"epoch{i}.pt" for i in range(EPOCHS))):
        checkpoint = weights/name
        digest = sha(checkpoint)
        if digest in seen:
            continue
        seen.add(digest)
        record = evaluate_checkpoint(checkpoint, val, run/(checkpoint.stem + ".jsonl"))
        require(record["checkpoint_sha256"] == digest, "Checkpoint changed during evaluation")
        candidates.append(record)
        save(run/"progress.json", dict(phase="evaluation", scored=len(candidates), at=now()))
    selected = max(candidates, key=rank_key)
    save(run/"result.json", dict(status="COMPLETED", baseline=candidate_metrics(baseline),
                                selected=candidate_metrics(selected), candidates=candidates,
                                final_test_used=False, finished_at=now(), **evidence))


def worker(work, node):
    state_file = work/"queue-status.json"
    _, names = SCHEDULE[node]
    states = read(state_file) if state_file.exists() else {name: {"status":"PENDING"} for name in names}
    save(state_file, states)
    for variant in names:
        if (work/"pause.request").exists():
            break
        if states[variant]["status"] in {"COMPLETED", "FAILED", "BLOCKED"}:
            continue
        run = work/f"{work.name}-{node}-{variant}"
        if run.exists():
            # Keep existing attempts and prevent restarting an interrupted job blindly.
            if (run/"result.json").is_file():
                states[variant] = {"status":"COMPLETED", "run_id":run.name,
                                   "result_sha256":sha(run/"result.json")}
            else:
                states[variant] = {"status":"BLOCKED", "run_id":run.name,
                                   "reason":"Existing unfinished attempt kept for inspection"}
            save(state_file, states)
            continue
        if (work.parent/"training/gpu0-training.lock").exists():
            states[variant] = {"status":"PENDING", "reason":"GPU busy"}
            save(state_file, states)
            return
        run.mkdir()
        command = [sys.executable, "-u", str(Path(__file__).resolve()), "job", str(work), node, variant]
        save(run/"command.json", {"command":command, "started_at":now()})
        with (run/"stdout.log").open("xb") as out, (run/"stderr.log").open("xb") as err:
            child = subprocess.Popen(command, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
            states[variant] = {"status":"RUNNING","pid":child.pid,"run_id":run.name,"started_at":now()}
            save(state_file, states)
            code = child.wait()
        result = run/"result.json"
        ok = code == 0 and result.is_file() and read(result)["status"] == "COMPLETED"
        states[variant].update(status="COMPLETED" if ok else "FAILED", exit_code=code, finished_at=now())
        if ok:
            states[variant]["result_sha256"] = sha(result)
        save(state_file, states)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preflight", "launch", "worker", "job"))
    parser.add_argument("work", type=Path)
    parser.add_argument("node", nargs="?", choices=SCHEDULE)
    parser.add_argument("variant", nargs="?")
    ns = parser.parse_args()
    if ns.action == "prepare":
        prepare(ns.work)
    elif ns.action == "preflight":
        from ultralytics import __version__
        import torch
        require(torch.cuda.is_available() and __version__=="8.4.152", "Unsupported CUDA environment")
        _, plan, val, _, variants = node_input(ns.work, ns.node)
        print(json.dumps({"node":ns.node, "unique_train":len(plan["training"]), "val":len(val), "variants":variants}))
    elif ns.action == "worker":
        with process_lock(ns.work/"queue.lock"):
            worker(ns.work, ns.node)
    elif ns.action == "job":
        run = ns.work/f"{ns.work.name}-{ns.node}-{ns.variant}"
        with gpu_training_lock(ns.work.parent/"training/gpu0-training.lock", owner=run.name):
            train_variant(ns.work, ns.node, ns.variant, run)
    else:
        log = ns.work/f"queue-{time.time_ns()}.log"
        with log.open("xb") as out:
            env = {**os.environ, "YOLO_AUTOINSTALL":"false", "PYTHONUTF8":"1", "KMP_DUPLICATE_LIB_OK":"TRUE"}
            job = subprocess.Popen([sys.executable,"-u",str(Path(__file__).resolve()),"worker",str(ns.work),ns.node],
                                   stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,env=env,
                                   creationflags=0x01000000|subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
        print(job.pid)


if __name__ == "__main__":
    main()
