"""Development-only actions invoked by the P430 overnight queue."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

from edge_threat_response.detection_evaluation import BBox, evaluate_boxes, iou
from edge_threat_response.detector_comparison import POLICY
from edge_threat_response.p430_evaluation import evaluate_checkpoint, make_truth, score_predictions
from edge_threat_response.p430_workflow import SOURCE_SHA, read, require, save, sha
from edge_threat_response.training import gpu_training_lock
from run_p430_integration import jsonl
from run_p430_site import (BUDGET, development_rows, draw_parents, execute, export_tile,
                           replace_tiles, score_mode, tile_predictions)
from run_p430_site_diagnostic import merge

PLAN_SHA = "8a92eefb8f4bf275d5ace1aae46edb37ad7c6fce02a0484e497fec96deb0a28c"
D1_SHA = "212a4b80e44674a3863daf240e127af797ac34f235a6e8356f23936b6348d190"


def pin_plan(base):
    plan_path = base / "plan.json"
    require(sha(plan_path) == PLAN_SHA, "Unexpected base development release")
    plan = read(plan_path)
    require(plan["summary"]["scope"] == "development_only"
            and sha(base / "protection.json") == plan["summary"]["protection_sha256"],
            "Development data protection receipt mismatch")
    return plan


def locked(rows, predictions, confidence):
    if confidence is None:
        predictions = [{**row, "detections": []} for row in predictions]
    result, matches = evaluate_boxes(make_truth(rows), predictions, {**POLICY, "confidence": confidence or .001})
    return {"tp": result["counts"]["tp"], "neg": result["counts"]["negative_images_with_fp"],
            "fp": result["counts"]["fp"], "small": sum(len(m["matches"]) for r,m in zip(rows,matches) if r["small"])}


def compare(checkpoint, rows, predictions, output):
    records = {key: score_predictions(checkpoint, rows[key], predictions[key], output / f"{key}.jsonl") for key in rows}
    point = locked(rows["dev_check"], predictions["dev_check"], records["tune"]["point"]["confidence"])
    return {**point, "ap50": records["dev_check"]["ap50"], "ap50_95": records["dev_check"]["ap50_95"],
            "tune": records["tune"]["point"], "predictions": records, "checkpoint_sha256": sha(checkpoint)}


def use_d1(settings):
    checkpoint = Path(settings["d1"])
    require(sha(checkpoint) == D1_SHA, "D1 differs from the selected checkpoint")
    return checkpoint


def gpu_name(settings):
    return "gpu0-training.lock" if settings["node"].startswith("pc") else f"{settings['uuid']}-training.lock"


def detection_variants(job, settings, base, plan, output, evidence):
    checkpoint = use_d1(settings)
    rows = development_rows(base, plan)
    if job["kind"] == "trace":
        rows = {"dev_check": rows["dev_check"]}
    variants = job.get("variants", {"native": {}})
    results = {}
    with gpu_training_lock(base.parent / "training" / gpu_name(settings), owner=job["id"]):
        for name, options in variants.items():
            path = output / name
            path.mkdir()
            predictions = {}
            for split, records in rows.items():
                if job["kind"] == "trace":
                    removed = []
                    predictions[split] = tile_predictions(checkpoint, records, trace=removed)
                    threshold = evidence["A0"]["data"]["metrics"]["confidence"]
                    truth = make_truth(records)
                    _, matches = evaluate_boxes(truth, predictions[split], {**POLICY, "confidence": threshold})
                    counts = Counter()
                    for row,tile,dropped,detail in zip(truth["images"],predictions[split],removed,matches,strict=True):
                        for index in detail["missed_truth_indices"]:
                            target = BBox(*row["knife_boxes_xyxy"][index])
                            overlaps = lambda boxes: max((iou(target,BBox(*box)) for box in boxes),default=0)
                            peak = overlaps([item["bbox_xyxy"] for item in tile["detections"]])
                            if peak>=.5:
                                counts["low_score_or_match"]+=1
                            elif overlaps(dropped["edge_removed"])>=.5:
                                counts["edge_removed"]+=1
                            elif overlaps(dropped["merge_removed"])>=.5:
                                counts["merge_removed"]+=1
                            else:
                                counts["localization" if peak>=.1 else "no_retained_overlap"]+=1
                    save(path/"trace.json",removed)
                    return {"counts": dict(counts), "misses": sum(counts.values())}
                if options.get("full"):
                    pred_file=path/f"{split}-whole.jsonl"
                    evaluate_checkpoint(checkpoint,records,pred_file,imgsz=options["full"])
                    predictions[split]=merge(jsonl(pred_file),tile_predictions(checkpoint,records,roi=options["roi"]))
                else:
                    predictions[split]=tile_predictions(checkpoint,records,window=options.get("window"),
                                                         imgsz=options.get("imgsz",640),clahe=options.get("clahe",False))
            results[name]=compare(checkpoint,rows,predictions,path)
    candidates=[name for name,metrics in results.items() if metrics["neg"]<=1]
    best=max(candidates,key=lambda name:(results[name]["small"],results[name]["tp"],-results[name]["neg"],
                                         results[name]["ap50_95"])) if candidates else None
    return {"variants":results,"best":best,"metrics":results[best] if best else {},
            "window":variants[best].get("window") if best else None}


def early_check(output, evidence):
    report={}
    for job_id in ("D1-3408","D1-3409"):
        report[job_id]=evidence[job_id]["data"]["early"]
    save(output/"early-checkpoints.json",report)
    return {"replicated_early":all(row["selected"].startswith("ema-batch-") for row in report.values()),"runs":report}


def replace_reviewed_negatives(deck, pool, keys, fraction):
    require(0 < fraction <= .20, "Invalid reviewed negative replacement fraction")
    targets = defaultdict(list)
    for key in keys:
        targets[pool[key]["source_group"]].append(key)
    selected_keys = set(keys)
    rng = random.Random(3407)
    replacements = []
    for epoch in deck:
        slots = defaultdict(list)
        for index, (key, tiled) in enumerate(epoch):
            row = pool[key]
            group = row["source_group"]
            if group in targets and row["domain"] == "p430" and row["n"] == 0 and not tiled and key not in selected_keys:
                slots[group].append(index)
        replaced = 0
        for group, candidates in sorted(targets.items()):
            eligible = slots[group]
            count = min(round(fraction * len(eligible)), 5 * len(candidates))
            if not count:
                continue
            sequence = sorted(candidates)
            rng.shuffle(sequence)
            for step, index in enumerate(rng.sample(eligible, count)):
                epoch[index] = (sequence[step % len(sequence)], False)
            replaced += count
        require(replaced > 0, "No equivalent reviewed negative slots were available")
        replacements.append(replaced)
    return replacements


def setup_train(job, settings, base, plan, output, evidence):
    params=dict(job.get("parameters",{}))
    work=base.parent/f"overnight-{job['id'].lower()}-{output.name}"
    work.mkdir(exist_ok=False)
    shutil.copy2(base/"protection.json",work/"protection.json")
    budget=params.get("budget",BUDGET)
    deck=plan["draws"]
    protect=read(base/"protection.json")
    protected={protect["edited_sha256"],*protect.get("original_sha256",[])}
    require(all(row["source_group"] not in protected and key not in protected for key,row in plan["pool"].items()),
            "Protected source appeared in the original train pool")
    window=evidence.get("A-TILE-GRID",{}).get("data",{}).get("window") if params.pop("best_tiles",False) else None
    share=params.pop("tile_share",None)
    if window:
        candidates=[row for row in plan["pool"].values() if row["domain"] in ("p430","cctv")]
        with ThreadPoolExecutor(max_workers=4) as workers:
            tiles=dict(item for item in workers.map(lambda r:export_tile(work,r,window),candidates) if item)
        plan["tiles"]=tiles
        plan["summary"]["tile_window"]=window
        share=share or .48
    if budget!=BUDGET:
        pools=defaultdict(list)
        for row in plan["pool"].values():
            pools[row["domain"]].append(row)
        deck=draw_parents(pools,plan["tiles"],budget,.48 if share is None else share)
    elif share is not None:
        deck=[replace_tiles(epoch,plan["tiles"],share) for epoch in deck]
    if params.pop("hard_negative",False):
        negative=read(Path(settings["approvals"])/job["approval"])
        require(negative["approved_development"] is True and negative["base_plan_sha256"]==PLAN_SHA,
                "Hard-negative approval did not match the release")
        held=set().union(*map(set,plan["validation"].values()))
        keys=negative["image_sha256"]
        require(keys and len(keys)==len(set(keys)) and not held.intersection(keys) and all(
            k in plan["pool"] and plan["pool"][k]["n"]==0 and plan["pool"][k]["domain"]=="p430" for k in keys),
            "Hard negatives must be verified P430 train-only files")
        fraction = params.pop("hard_negative_fraction", None)
        if fraction is not None:
            mine = evidence[job["after"][0]]["data"]
            require(mine["scope"] == "development_train_review_candidates" and mine["base_plan_sha256"] == PLAN_SHA
                    and mine["reviewed_manifest_sha256"] == SOURCE_SHA
                    and set(keys) == {item["image_sha256"] for item in mine["candidates"]},
                    "Hard-negative manifest does not match the verified mining receipt")
            plan["summary"]["hard_negative_replacements"] = replace_reviewed_negatives(
                deck, plan["pool"], keys, fraction
            )
            plan["summary"]["hard_negative_fraction"] = fraction
        else:
            rng=random.Random(3407)
            for epoch in deck:
                eligible=[i for i,(k,tiled) in enumerate(epoch) if not tiled and plan["pool"][k]["domain"]=="p430"
                          and plan["pool"][k]["n"]==0]
                require(eligible,"No equivalent negative slot for the approved images")
                for i in rng.sample(eligible,min(len(keys),max(1,len(eligible)//5))):
                    epoch[i]=(rng.choice(keys),False)
    if not window:
        for key in {key for epoch in deck for key,tiled in epoch if tiled}:
            for folder,suffix in (("images",".jpg"),("labels",".txt")):
                source=base/"tiles"/folder/(key+suffix)
                if source.is_file():
                    destination=work/"tiles"/folder/source.name
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    try:
                        import os
                        os.link(source,destination)
                    except OSError:
                        shutil.copyfile(source,destination)
    plan["draws"]=deck
    plan["summary"]["parent_plan_sha256"]=PLAN_SHA
    plan["summary"]["draws_per_epoch"]=budget
    plan["summary"]["tiles_per_epoch"]=[sum(tiled for _,tiled in epoch) for epoch in deck]
    save(work/"plan.json",plan)
    runner=Path(__file__).with_name("run_p430_site.py")
    release={"variant":"followup","seed":3407,"plan_sha256":sha(work/"plan.json"),
             "protection_sha256":sha(work/"protection.json"),"runner_sha256":sha(runner),"experiment":params}
    model=params.pop("model",None)
    if model:
        weight_info=settings["weights"][model]
        source=Path(weight_info["path"])
        require(sha(source)==weight_info["sha256"],"Large model initialization changed")
        shutil.copy2(source,work/model)
        release.update(variant="coco",model=model,initial_sha256=weight_info["sha256"])
    if params.pop("teacher",False):
        teacher=Path(settings["approvals"])/"A-DISTILL-teacher.pt"
        receipt=read(Path(settings["approvals"])/"A-DISTILL.json")
        require(receipt["scope"]=="development_only" and sha(teacher)==receipt["teacher_sha256"],"Teacher changed")
        shutil.copy2(teacher,work/"teacher.pt")
        params["teacher_sha256"]=receipt["teacher_sha256"]
    save(work/"release.json",release)
    save(output/"work.json",{"path":str(work),"plan_sha256":sha(work/"plan.json")})
    execute(work,settings["trainer_node"])
    return site_receipt(work/f"{work.name}-{settings['trainer_node']}")


def site_receipt(run):
    state=read(run/"state.json")
    result=run/"result.json"
    require(state["status"]=="COMPLETED" and state["result_sha256"]==sha(result),"Missing or inconsistent result receipt")
    tile=read(result)["result"]["tile640"]
    name=tile["selected_checkpoint"]
    record=tile["dev_check"][name]
    point=record["point"]
    checkpoint=(run if name.startswith("ema-batch-") else run/"train/weights")/name
    require(sha(checkpoint)==record["checkpoint_sha256"],"Selected checkpoint changed")
    return {"metrics":{"small":point["small_tp"],"tp":point["tp"],"neg":point["negative_frames_flagged"],
                        "fp":point["fp_boxes"],"ap50":record["ap50"],"ap50_95":record["ap50_95"]},
            "checkpoint":str(checkpoint),"checkpoint_sha256":record["checkpoint_sha256"],"local_result":str(result),
            "result_sha256":state["result_sha256"],"early":{"selected":name,
            "checkpoints":[{key:item[key] for key in ("checkpoint","checkpoint_sha256","point","ap50_95")}
                           for item in tile["tune"]]}}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ("task","output"):
        cli.add_argument(name,type=Path)
    args=cli.parse_args()
    payload=read(args.task)
    settings,job,evidence=[payload[k] for k in ("settings","job","evidence")]
    base=Path(settings["base"])
    kind=job["kind"]
    if kind=="early":
        result=early_check(args.output,evidence)
    elif kind in ("grid","trace","diagnostic"):
        result=detection_variants(job,settings,base,pin_plan(base),args.output,evidence)
    elif kind=="train":
        result=setup_train(job,settings,base,pin_plan(base),args.output,evidence)
    elif kind=="approved":
        approval=read(Path(settings["approvals"])/f"{job['id']}.json")
        require(approval["scope"]=="development_only" and approval["base_plan_sha256"]==PLAN_SHA,
                "Approved executor is outside the development release")
        require(all(isinstance(word,str) for word in approval["argv"]),"Expected an argument list")
        subprocess.run(approval["argv"],cwd=args.output,check=True)
        result=read(args.output/"evidence.json")
    else:
        raise ValueError(f"Unknown action: {kind}")
    save(args.output/"result.json",result)


if __name__=="__main__":
    main()
