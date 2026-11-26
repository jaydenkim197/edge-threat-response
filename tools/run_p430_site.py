"""Train full-frame/tiling and backbone-freeze controls for the P430 site."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
import os
from pathlib import Path
import random
import subprocess
import sys

from edge_threat_response.p430_evaluation import evaluate_checkpoint, make_truth, rank_key, score_predictions
from edge_threat_response.p430_queue import process_lock
from edge_threat_response.p430_workflow import MODEL_SHA, SOURCE_SHA, now, read, require, save, sha
from edge_threat_response.training import gpu_training_lock, run_training
from run_p430_integration import jsonl, paths, repeated

ROUNDS = {"pc11": (False, False), "pc12": (False, True),
          "pc13": (True, False), "pc14": (True, True),
          "lab0": (True, False), "lab1": (True, False), "lab2": (True, False), "lab5": (True, False)}
BUDGET = {"p430": 4096, "cctv": 2458, "m2": 1638}
EPOCHS = 12
DRAWS = sum(BUDGET.values())
FOLDS = ("ee22020ec86614adbade9472f23c79e2fe4942ddd6955661109d6840e52d5123",
         "63a32f9a7cb1db4d1957cce7373f37ce065dee40de4d6adb543f69680d86179b")
GUARD = 10


def split_development(rows):
    sessions = defaultdict(list)
    for row in rows:
        sessions[row["session"]].append(row)
    parts = defaultdict(list)
    cuts = {}
    for session, items in sorted(sessions.items()):
        items.sort(key=lambda r: r["timestamp_s"])
        # Pick cut points without inference. Require a confirmed negative
        # neighborhood so a visible sequence isn't severed at a boundary.
        clean = [row["timestamp_s"] for i, row in enumerate(items[2:-2], 2)
                 if all(not r["knife_boxes"] for r in items[i-2:i+3])
                 and items[i+2]["timestamp_s"] - items[i-2]["timestamp_s"] <= 6]
        require(len(clean) > 4, "Insufficient negative neighborhoods")
        span = items[-1]["timestamp_s"] - items[0]["timestamp_s"]
        boundaries = [min(clean, key=lambda t: abs(t - (items[0]["timestamp_s"] + frac*span)))
                      for frac in (.18, .36, .60, .78)]
        require(all(b-a > 2*GUARD for a,b in zip(boundaries, boundaries[1:])), "Overlapping development blocks")
        cuts[session] = boundaries
        a,b,c,d = boundaries
        for row in items:
            t = row["timestamp_s"]
            if any(abs(t-cut) <= GUARD for cut in boundaries):
                name = "embargo"
            elif a < t < b:
                name = "tune"
            elif c < t < d:
                name = "dev_check"
            else:
                name = "train"
            parts[name].append(row)
    for name in ("train", "tune", "dev_check"):
        require({bool(r["knife_boxes"]) for r in parts[name]} == {False, True}, f"{name} needs positive and negative labels")
    return parts, cuts


def regions(w, h):
    if w < 768 or h < 640 or (w,h) == (768,640):
        return []
    # 3 by 2 grid matches the earlier 1920x1080 evaluation. The two
    # edge positions are pinned to the image boundary.
    return [(x,y,x+768,y+640) for y in (0,h-640) for x in (0,(w-768)//2,w-768) if x+768 <= w]


def normalized_crop(boxes, region):
    x1,y1,x2,y2=region
    labels=[]
    for x,y,w,h in boxes:
        a,c=max(x-w/2,x1),min(x+w/2,x2)
        b,d=max(y-h/2,y1),min(y+h/2,y2)
        if c <= a or d <= b:
            continue
        if (c-a)*(d-b) < .8*w*h:
            return None  # Partial visible knife must never act as background.
        labels.append(((a+c-2*x1)/(2*(x2-x1)),(b+d-2*y1)/(2*(y2-y1)),
                       (c-a)/(x2-x1),(d-b)/(y2-y1)))
    return labels


def original_boxes(label):
    rows=[]
    for line in label.read_text(encoding="utf-8").splitlines():
        cid,x,y,w,h=map(float,line.split())
        require(cid==0 and -1e-6 <= x-w/2 < x+w/2 <= 1+1e-6 and
                -1e-6 <= y-h/2 < y+h/2 <= 1+1e-6, "Invalid YOLO label")
        rows.append((x,y,w,h))
    return rows


def export_tile(work,r):
    from PIL import Image

    image_path,label_path=paths(work,r)
    require(sha(image_path)==r["image_sha256"] and sha(label_path)==r["label_sha256"], "Aliased or changed tile parent")
    labels=original_boxes(label_path)
    require(len(labels)==r["n"], "Tile label count mismatch")
    with Image.open(image_path) as image:
        w,h=image.size
        available=regions(w,h)
        # Larger external frames are admitted through the older reviewed range;
        # outside that native grid use the parent rather than leave gaps.
        if w>2304 or h>1280 or not available:
            return None
        boxes=[(x*w,y*h,dw*w,dh*h) for x,y,dw,dh in labels]
        valid=[]
        for region in dict.fromkeys(available):
            retained=normalized_crop(boxes,region)
            if retained is not None and bool(retained)==bool(labels):
                valid.append((region,retained))
        if not valid:
            return None
        key=r["image_sha256"]
        crop, coords=valid[int(key[:12],16)%len(valid)]
        tile=work/"tiles/images"/(key+".jpg")
        output=work/"tiles/labels"/(key+".txt")
        require(not tile.exists() and not output.exists(), "Tile output already exists")
        image.crop(crop).convert("RGB").save(tile,quality=95,subsampling=0)
        output.write_text("".join("0 "+" ".join(f"{v:.9f}" for v in box)+"\n" for box in coords),encoding="ascii")
    restored=original_boxes(output)
    require(len(restored)==len(coords) and all(abs(x-y)<1e-8 for a,b in zip(restored,coords,strict=True)
                                               for x,y in zip(a,b,strict=True)), "Tile labels changed in serialization")
    return key, {"image_sha256":sha(tile),"label_sha256":sha(output),"region":list(crop)}


def draw_parents(pools,tiles):
    rng=random.Random(3407)
    # Interleave public source groups first, then cycle to cover the whole pool
    # before repeating public images in later epochs.
    by_group=defaultdict(list)
    for r in pools["m2"]:
        by_group[r["group"]].append(r["image_sha256"])
    for group in by_group.values():
        rng.shuffle(group)
    public=[]
    keys=sorted(by_group)
    rng.shuffle(keys)
    while keys:
        for key in keys:
            public.append(by_group[key].pop())
        keys=[key for key in keys if by_group[key]]
    decks=[]
    for epoch in range(EPOCHS):
        start=epoch*BUDGET["m2"]
        draw=[(public[i%len(public)],False) for i in range(start,start+BUDGET["m2"])]
        for domain in ("p430","cctv"):
            source=pools[domain]
            count=BUDGET[domain]
            positives=[r for r in source if r["n"]]
            negatives=[r for r in source if not r["n"]]
            pos=round(count*len(positives)/len(source))
            for group,number in ((positives,pos),(negatives,count-pos)):
                cohort=repeated(group,number,rng)
                quota=round(.60*number)
                eligible=[i for i,r in enumerate(cohort) if r["image_sha256"] in tiles]
                rng.shuffle(eligible)
                selected=set(eligible[:quota])
                draw.extend((r["image_sha256"],i in selected) for i,r in enumerate(cohort))
        rng.shuffle(draw)
        require(len(draw)==DRAWS,"Unexpected draw count")
        decks.append(draw)
    return decks


def prepare(work):
    old=work.parent/"p430-integrated-20261122-v1"
    original=work.parent/"p430-t1-20261120-v1"
    seal=read(work/"protection.json")
    require(seal["capture_date"]=="2026-11-24" and seal["independent_recording_confirmed"]
            and len(seal["edited_sha256"])==64,"Final test provenance confirmation is required")
    capture=original/"dataset/manifest.jsonl"
    require(sha(capture)==SOURCE_SHA and sha(original/"initial.pt")==MODEL_SHA,"Prior input changed")
    rows=jsonl(capture)
    require(len(rows)==1901 and len({r["image_sha256"] for r in rows})==1901,"Invalid reviewed capture set")
    require(seal["edited_sha256"] not in {r["source_video_sha256"] for r in rows} and
            not set(seal.get("original_sha256",[])) & {r["source_video_sha256"] for r in rows},
            "Final and development recording overlap")
    sources={}
    for index,digest in enumerate(FOLDS,1):
        manifest=old/f"fold-{index}.json"
        require(sha(manifest)==digest,"Prior audited plan changed")
        for key,row in read(manifest)["training"].items():
            require(key not in sources or sources[key]==row,"Prior fold identity mismatch")
            sources[key]=row
    require(len(sources)==14920,"Prior train pools changed")
    split,cuts=split_development(rows)
    for directory in ("tiles/images","tiles/labels"):
        (work/directory).mkdir(parents=True,exist_ok=False)
    train=set(r["image_sha256"] for r in split["train"])
    held={name:{r["image_sha256"] for r in split[name]} for name in ("tune","dev_check","embargo")}
    pool={key:r for key,r in sources.items() if r["domain"]!="p430" or key in train}
    require(all(not (pool.keys()&keys) for keys in held.values()),"Development leakage")
    for r in split["train"]:
        pool[r["image_sha256"]]["group"]=f"{r['session']}:{int(r['timestamp_s']//30)}"
    with ThreadPoolExecutor(max_workers=4) as workers:
        generated=list(workers.map(lambda r:export_tile(work,r), (r for r in pool.values() if r["domain"] in {"p430","cctv"})))
    tiles=dict(x for x in generated if x is not None)
    pools={domain:[r for r in pool.values() if r["domain"]==domain] for domain in BUDGET}
    decks=draw_parents(pools,tiles)
    summary={"split":{k:{"count":len(v),"positive":sum(bool(r["knife_boxes"]) for r in v),
                       "small":sum(sources[r["image_sha256"]]["small"] for r in v)} for k,v in split.items()},
             "cuts_s":cuts,"embargo_s":GUARD,"eligible_by_domain":{k:len(v) for k,v in pools.items()},
             "seen_by_domain":dict(Counter(pool[key]["domain"] for key in {key for deck in decks for key,_ in deck})),
             "tile_views":len(tiles),"tiles_per_epoch":[sum(flag for _,flag in deck) for deck in decks],
             "draws_per_epoch":BUDGET,"scope":"development_only","protection_sha256":sha(work/"protection.json")}
    save(work/"plan.json",{"summary":summary,"pool":pool,"validation":{k:[r["image_sha256"] for r in split[k]] for k in ("tune","dev_check")},
                           "tiles":tiles,"draws":decks})
    print(summary,flush=True)


def input_paths(work, plan, key, tiled):
    if tiled:
        return work/"tiles/images"/(key+".jpg"), work/"tiles/labels"/(key+".txt")
    return paths(work, plan["pool"][key])


def verify_inputs(work, plan, tiled):
    seen={key for deck in plan["draws"] for key,_ in deck}
    require(all(len(deck)==DRAWS for deck in plan["draws"]) and len(plan["draws"])==EPOCHS,"Invalid draw budget")
    require(all(Counter(plan["pool"][key]["domain"] for key,_ in deck)==BUDGET for deck in plan["draws"]),
            "Source budget changed")
    held=set().union(*map(set,plan["validation"].values()))
    require(not (held&seen),"Training draws contain protected development frames")
    for key in seen:
        r=plan["pool"][key]
        image,label=paths(work,r)
        require(sha(image)==key and sha(label)==r["label_sha256"],"Training parent changed")
    if tiled:
        for directory in ("tiles/images","tiles/labels"):
            (work/directory).mkdir(parents=True,exist_ok=True)
        for key in {k for deck in plan["draws"] for k,use in deck if use}:
            path,label=input_paths(work,plan,key,True)
            evidence=plan["tiles"][key]
            if not path.exists() and not label.exists():
                require(export_tile(work,plan["pool"][key])==(key,evidence),"Cross-PC tile output mismatch")
            require(sha(path)==evidence["image_sha256"] and sha(label)==evidence["label_sha256"],"Tile changed")


def development_rows(work, plan):
    root=work.parent/"p430-t1-20261120-v1/dataset"
    manifest=root/"manifest.jsonl"
    require(sha(manifest)==SOURCE_SHA,"Prior development labels changed")
    all_rows={r["image_sha256"]:r for r in jsonl(manifest)}
    result={}
    for split,keys in plan["validation"].items():
        result[split]=[]
        for key in keys:
            row=all_rows[key]
            image=root/"images"/Path(row["image"]).name
            label=root/"labels"/image.with_suffix(".txt").name
            require(sha(image)==key and sha(label)==row["label_sha256"],"Validation pair changed")
            boxes=original_boxes(label)
            require(len(boxes)==row["knife_boxes"],"Validation knife count changed")
            result[split].append({**row,"image_file":str(image),"boxes":boxes,
                                  "small":any(min(w*960,h*540)<16 for _,_,w,h in boxes)})
    return result


def tile_predictions(checkpoint, rows, *, restore=None, clahe=False):
    import torch
    from PIL import Image
    from torchvision.ops import nms
    from ultralytics import YOLO
    from edge_threat_response.detector_comparison import canonical_prediction

    model=YOLO(checkpoint)
    require(model.names=={0:"knife"},"Unexpected knife detector classes")
    if clahe:
        import cv2
        import numpy as np

        enhancement=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8))
    output=[]
    for row,image in zip(rows,make_truth(rows)["images"],strict=True):
        with Image.open(row["image_file"]) as parent:
            require(parent.size==(1920,1080),"Tile evaluation expects reviewed P430 dimensions")
            grid=regions(*parent.size)
            source=parent.convert("RGB")
            if clahe:
                lab=cv2.cvtColor(np.asarray(source),cv2.COLOR_RGB2LAB)
                lab[:,:,0]=enhancement.apply(lab[:,:,0])
                source=Image.fromarray(cv2.cvtColor(lab,cv2.COLOR_LAB2RGB))
            chips=[source.crop(region) for region in grid]
            if restore is not None:
                chips=[chip.resize((chip.width//2,chip.height//2),Image.Resampling.BOX)
                       .resize(chip.size,restore) for chip in chips]
        predicted=model.predict(chips,imgsz=640,batch=len(chips),rect=False,conf=.001,device=0,
                                iou=.7,classes=[0],max_det=100,verbose=False)
        boxes,scores=[],[]
        for result,(x,y,x2,y2) in zip(predicted,grid,strict=True):
            for (a,b,c,d),confidence in zip(result.boxes.xyxy.tolist(),result.boxes.conf.tolist(),strict=True):
                if (x>0 and a<3) or (y>0 and b<3) or (x2<1920 and c>x2-x-3) or (y2<1080 and d>y2-y-3):
                    continue
                boxes.append([a+x,b+y,c+x,d+y])
                scores.append(confidence)
        keep=nms(torch.tensor(boxes,dtype=torch.float32),torch.tensor(scores),.55).tolist()[:300] if boxes else []
        prediction,_=canonical_prediction(image,[boxes[i] for i in keep],[scores[i] for i in keep],[0]*len(keep),0)
        output.append(prediction)
    return output


def score_mode(checkpoint, rows, output, mode, threshold=None, locked=False):
    from edge_threat_response.detection_evaluation import evaluate_boxes
    from edge_threat_response.detector_comparison import POLICY

    if mode=="tile640":
        predictions=tile_predictions(checkpoint,rows)
        record=score_predictions(checkpoint,rows,predictions,output)
    else:
        record=evaluate_checkpoint(checkpoint,rows,output)
    if locked:
        predictions=jsonl(output)
        if threshold is None:
            predictions=[{**r,"detections":[]} for r in predictions]
        scores,matches=evaluate_boxes(make_truth(rows),predictions,
                                      {**POLICY,"confidence":threshold if threshold is not None else .001})
        record["point"]={"confidence":threshold,"tp":scores["counts"]["tp"],"fp_boxes":scores["counts"]["fp"],
                         "negative_frames_flagged":scores["counts"]["negative_images_with_fp"],
                         "small_tp":sum(len(v["matches"]) for r,v in zip(rows,matches,strict=True) if r["small"])}
        record["threshold_source"]="tune"
    return record


def trainer_factory(draw_paths, val_paths, freeze, state, *, phase2=False, coco=False, model_yaml=None, seed=None):
    import torch
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionTrainer

    class PlannedSampler(torch.utils.data.Sampler):
        def __init__(self, indices):
            self.indices=indices
            self.epoch=0

        def __len__(self):
            return DRAWS

        def __iter__(self):
            return iter(self.indices[self.epoch])

    class SiteTrainer(DetectionTrainer):
        def get_dataloader(self, dataset_path, batch_size=16, rank=0, mode="train"):
            loader=super().get_dataloader(dataset_path,batch_size,rank,mode)
            paths_on_loader=list(map(Path,loader.dataset.im_files))
            if mode=="val":
                require(set(paths_on_loader)==set(val_paths),"Unexpected validation loader")
                return loader
            unique={p:i for i,p in enumerate(paths_on_loader)}
            require(len(unique)==len(paths_on_loader) and set(unique)==set().union(*map(set,draw_paths)),
                    "Unexpected training image inventory")
            sampler=PlannedSampler([[unique[p] for p in deck] for deck in draw_paths])
            loader.batch_sampler.sampler.sampler=sampler
            self.site_sampler=sampler
            loader.reset()
            require(len(loader)==DRAWS//batch_size and batch_size==8,"Actual batch budget changed")
            return loader

    class SiteModel(YOLO):
        def train(self, **kwargs):
            return super().train(trainer=SiteTrainer, **kwargs)

    def factory(checkpoint):
        model=SiteModel(checkpoint)
        expected_classes = len(model.names)==80 and model.names[0]=="person" if coco else model.names=={0:"knife"}
        require(expected_classes and len(model.model.yaml["backbone"])==11,"Unverified model layout or classes")
        if model_yaml is not None:
            torch.manual_seed(seed)
            model=SiteModel(model_yaml).load(checkpoint)
            require(len(model.model.yaml["backbone"])==11 and len(model.model.model[-1].f)==4,
                    "Expected a YOLO26 P2–P5 detection head")
        counts=Counter()
        verified={}

        def start(trainer):
            trainer.site_sampler.epoch=trainer.epoch
            trainer.train_loader.reset()

        def first_batch(trainer):
            optimizer_parameters=[p for group in trainer.optimizer.param_groups for p in group["params"]]
            if counts[trainer.epoch]==0 and trainer.epoch==0:
                backbone=trainer.model.model[:11]
                params=list(backbone.parameters())
                require(params and all(p.requires_grad != freeze for p in params),"Backbone freeze contract mismatch")
                require(any(p.requires_grad for p in optimizer_parameters),"No trainable optimizer parameters")
                if freeze:
                    require(all(not b.training for b in backbone.modules() if isinstance(b,torch.nn.BatchNorm2d)),
                            "Frozen backbone BN statistics still adaptive")
                    verified.update({k:v.detach().cpu().clone() for k,v in backbone.state_dict().items()})
                save(state,{"status":"RUNNING","phase":"training","epoch":1,"epochs":EPOCHS,
                            "train_batches":len(trainer.train_loader),"freeze_verified":freeze,"at":now()})
            counts[trainer.epoch]+=1

        def epoch_done(trainer):
            if phase2 and counts[trainer.epoch]==0 and all(counts[e]==DRAWS//8 for e in range(EPOCHS)):
                return  # Final evaluation callback has no additional training batches.
            require(counts[trainer.epoch]==DRAWS//8,"Observed batch count differs")
            if freeze:
                end=trainer.model.model[:11].state_dict()
                require(all(torch.equal(value,end[name].detach().cpu()) for name,value in verified.items()),
                        "Frozen backbone parameters or buffers changed")
            save(state,{"status":"RUNNING","phase":"training","epochs_completed":trainer.epoch+1,"epochs":EPOCHS,
                        "train_batches":counts[trainer.epoch],"at":now()})

        model.add_callback("on_train_epoch_start",start)
        model.add_callback("on_train_batch_start",first_batch)
        model.add_callback("on_train_epoch_end",epoch_done)
        if phase2:
            def observe(trainer):
                batch=counts[trainer.epoch]
                if batch%64==0:
                    save(state,{"status":"RUNNING","phase":"training","epoch":trainer.epoch+1,
                                "epochs":EPOCHS,"batch":batch,"train_batches":DRAWS//8,"at":now()})
                if trainer.epoch==0 and batch in (256,512,768,1024):
                    target=state.parent/f"ema-batch-{batch:04d}.pt"
                    temporary=target.with_suffix(".tmp")
                    torch.save({"ema":deepcopy(trainer.ema.ema).half(),
                                "train_args":vars(trainer.args)},temporary)
                    temporary.replace(target)
                    save(target.with_suffix(".json"),{"batch":batch,"sha256":sha(target),
                         "ema_updates":trainer.ema.updates,"lr":[g["lr"] for g in trainer.optimizer.param_groups]})
            model.add_callback("on_train_batch_end",observe)
        return model
    return factory


def execute(work,node, *, recovery=False):
    import torch
    from ultralytics import __version__

    require(torch.cuda.is_available() and __version__=="8.4.152","Unexpected or unavailable GPU environment")
    tiled,freeze=ROUNDS[node]
    pin=read(work/"release.json")
    variant=pin.get("variant")
    require(variant in (None,"replicate","coco","p2"),"Unexpected site recipe")
    if variant is not None:
        require(pin.get("seed") in (3407,3408,3409),"Unpinned site training seed")
        tiled,freeze=True,False
    plan_path=work/"plan.json"
    require(sha(plan_path)==pin["plan_sha256"] and sha(work/"protection.json")==pin["protection_sha256"]
            and sha(Path(__file__).resolve())==pin["runner_sha256"],"Run release changed")
    plan=read(plan_path)
    require(plan["summary"]["protection_sha256"]==pin["protection_sha256"]
            and plan["summary"]["scope"]=="development_only","Development-only protection contract failed")
    run=work/f"{work.name}-{node}"
    state=run/"state.json"
    if recovery:
        prior=read(state)
        invocation=run/"train-invocation.json"
        receipt=read(invocation)
        require(prior=={"status":"FAILED","reason":"Observed batch count differs","at":prior["at"]}
                and receipt["status"]=="failed" and receipt["error"]=="ValueError: Observed batch count differs"
                and receipt["dataset_manifest"]["sha256"]==pin["plan_sha256"]
                and receipt["model_source"]["sha256"]==MODEL_SHA
                and receipt["config_sha256"]==sha(run/"profile.json"),
                "Evaluation-only recovery requires the known final-callback failure")
    else:
        run.mkdir(exist_ok=False)
    initial=work.parent/"p430-t1-20261120-v1/initial.pt"
    require(sha(initial)==MODEL_SHA,"Prior initial weight changed")
    checkpoint=initial
    model_yaml=None
    if variant in ("coco","p2"):
        require(pin.get("model") in ("yolo26n.pt","yolo26s.pt","yolo26m.pt"),"Unexpected COCO weight")
        checkpoint=work/pin["model"]
        require(sha(checkpoint)==pin["initial_sha256"],"COCO weight hash changed")
    if variant=="p2":
        model_yaml=work/"yolo26n-p2.yaml"
        require(pin["model"]=="yolo26n.pt" and sha(model_yaml)==pin["architecture_sha256"],"P2 source changed")
    previous=work.parent/"p430-t1-20261120-v1"
    sys.path.insert(0,str(previous/"evaluation-deps"))
    lock_name="gpu0-training.lock"
    if os.name!="nt" and node.startswith("lab"):
        visible=os.environ.get("CUDA_VISIBLE_DEVICES","")
        require(visible.startswith("GPU-") and visible[4:].replace("-","").isalnum()
                and torch.cuda.device_count()==1,"Expected one masked physical GPU")
        lock_name=f"{visible}-training.lock"
    with gpu_training_lock(work.parent/"training"/lock_name,owner=run.name):
        try:
            save(state,{"status":"RUNNING","phase":"preflight","at":now()})
            val=development_rows(work,plan)
            if not recovery:
                verify_inputs(work,plan,tiled)
                geometry=[[input_paths(work,plan,key,tiled and use)[0] for key,use in deck] for deck in plan["draws"]]
                eval_list=[Path(r["image_file"]) for r in val["tune"]]
                for name,files in (("train",sorted(set().union(*map(set,geometry)))),("val",eval_list)):
                    (run/f"{name}.txt").write_text("".join(x.as_posix()+"\n" for x in files),encoding="utf-8")
                data=run/"data.yaml"
                data.write_text(f"path: {run.as_posix()}\ntrain: train.txt\nval: val.txt\nnames:\n  0: knife\n",encoding="utf-8")
                options={**read(previous/"config.json")["args"],"epochs":EPOCHS,"imgsz":640,"nbs":8,
                         "lr0":.0001,"save_period":3,"freeze":11 if freeze else 0}
                if variant is not None:
                    options["seed"]=pin["seed"]
                profile=run/"profile.json"
                save(profile,{"schema_version":1,"profile_id":run.name,"model":str(checkpoint),
                              "task":"detect","run_name":"train","arguments":options})
                run_training(profile,data_yaml=data,output_dir=run,dataset_manifest=plan_path,
                             model_factory=trainer_factory(geometry,eval_list,freeze,state,
                                                           phase2=variant is not None,coco=variant in ("coco","p2"),
                                                           model_yaml=model_yaml,seed=pin.get("seed")))
            with (run/"train/results.csv").open(newline="",encoding="utf-8") as stream:
                epochs=[int(row["epoch"]) for row in csv.DictReader(stream)]
            require(epochs==list(range(1,EPOCHS+1)),"Missing epochs")
            weights=run/"train/weights"
            candidates=[initial,weights/"best.pt",weights/"last.pt",
                        *(weights/f"epoch{epoch}.pt" for epoch in range(0,EPOCHS,3))]
            if variant is not None:
                candidates.extend(run/f"ema-batch-{batch:04d}.pt" for batch in (256,512,768,1024))
            require(all(p.is_file() and p.stat().st_size>0 for p in candidates),"Missing training checkpoints")
            if recovery:
                summary=run/"evaluation-recovery.json"
                require(not summary.exists(),"Prior recovery already exists")
                save(summary,{"training_state":prior,"training_receipt_sha256":sha(invocation),
                              "results_csv_sha256":sha(run/"train/results.csv"),"epochs":epochs,
                              "checkpoints":{p.name:sha(p) for p in candidates},"at":now()})
            unique=list({sha(p):p for p in reversed(candidates)}.values())
            save(state,{"status":"RUNNING","phase":"evaluation","at":now()})
            report={}
            for mode in ("full960","tile640"):
                tune=[score_mode(p,val["tune"],run/f"tune-{mode}-{p.stem}.jsonl",mode) for p in unique]
                best=max((r for r in tune if r["checkpoint_sha256"]!=MODEL_SHA),key=rank_key)
                baseline=next(r for r in tune if r["checkpoint_sha256"]==MODEL_SHA)
                report[mode]={"tune":tune,"selected_checkpoint":best["checkpoint"],
                              "dev_check":{r["checkpoint"]:score_mode(
                                  initial if r is baseline else
                                  (run if r["checkpoint"].startswith("ema-batch-") else weights)/r["checkpoint"],val["dev_check"],
                                  run/f"dev-{mode}-{r['checkpoint']}.jsonl",mode,
                                  threshold=r["point"]["confidence"],locked=True) for r in (baseline,best)}}
                save(run/"evaluation.json",report)
            save(run/"result.json",{"status":"COMPLETED","mode":node,"tiled":tiled,"freeze":freeze,"scope":"development",
                                    "release":pin,"result":report,"finished_at":now()})
            save(state,{"status":"COMPLETED","phase":"evaluation","at":now(),"result_sha256":sha(run/"result.json")})
        except Exception as exc:
            save(state,{"status":"FAILED","reason":str(exc),"at":now()})
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("prepare","launch","worker","launch-evaluation","evaluate"))
    parser.add_argument("work",type=Path)
    parser.add_argument("node",nargs="?",choices=ROUNDS)
    ns=parser.parse_args()
    if ns.action=="prepare":
        prepare(ns.work)
        return
    require(ns.node is not None,"Missing GPU node")
    if ns.action in {"worker","evaluate"}:
        with process_lock(ns.work/f"{ns.node}.lock"):
            execute(ns.work,ns.node,recovery=ns.action=="evaluate")
        return
    evaluation=ns.action=="launch-evaluation"
    label=f"{ns.node}-evaluation" if evaluation else ns.node
    action="evaluate" if evaluation else "worker"
    with (ns.work/f"{label}-stdout.log").open("xb") as out,(ns.work/f"{label}-stderr.log").open("xb") as err:
        env={**os.environ,"YOLO_AUTOINSTALL":"false","PYTHONUTF8":"1","KMP_DUPLICATE_LIB_OK":"TRUE"}
        job=subprocess.Popen([sys.executable,"-u",str(Path(__file__).resolve()),action,str(ns.work),ns.node],
                             stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env,
                             creationflags=0x01000000|subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
    print(job.pid)


if __name__=="__main__":
    main()
