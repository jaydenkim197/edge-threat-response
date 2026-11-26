"""Compare cached predictions without reopening the protected test set."""

from argparse import ArgumentParser
from pathlib import Path

from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.detector_comparison import POLICY
from edge_threat_response.p430_evaluation import make_truth
from edge_threat_response.p430_workflow import save
from p430_followup_actions import compare, locked, pin_plan, use_d1
from run_p430_integration import jsonl
from run_p430_site import development_rows
from run_p430_site_diagnostic import merge


def score_features(predictions):
    import numpy as np

    values=[]
    for frame in predictions:
        for detection in frame["detections"]:
            x1,y1,x2,y2=detection["bbox_xyxy"]
            score=max(1e-6,min(1-1e-6,detection["confidence"]))
            area=(x2-x1)*(y2-y1)/(1920*1080)
            # This is distance to the known grid lines, not the contributing tile.
            edge=min(abs((x1+x2)/2-x)/1920 for x in (576,768,1152,1344))
            edge=min(edge,*(abs((y1+y2)/2-y)/1080 for y in (440,640)))
            values.append((np.log(score/(1-score)),np.log(area+1e-8),edge))
    return np.asarray(values,dtype=float).reshape(-1,3)


def calibrate(rows, cache):
    import numpy as np
    def sigmoid(value):
        return 1/(1+np.exp(-np.clip(value,-30,30)))

    _,details=evaluate_boxes(make_truth(rows["tune"]),cache["tune"],{**POLICY,"confidence":.001})
    truth=np.asarray([index in {item["prediction_index"] for item in detail["matches"]}
                      for detail,frame in zip(details,cache["tune"],strict=True)
                      for index in range(len(frame["detections"]))],dtype=float)
    raw=score_features(cache["tune"])
    if not truth.any() or truth.all():
        raise ValueError("Score calibration requires both matched and unmatched tune predictions")
    mean=raw.mean(axis=0)
    sigma=raw.std(axis=0).clip(1e-6)
    design=(raw-mean)/sigma
    design=np.column_stack((np.ones(len(design)),design))

    weights=np.zeros(4)
    for _ in range(400):
        gradient=design.T@(sigmoid(design@weights)-truth)/len(truth)+.02*np.r_[0,weights[1:]]
        weights-=.3*gradient
        weights[1]=max(0.0,weights[1])

    transformed={}
    for split,pred in cache.items():
        feature=(score_features(pred)-mean)/sigma
        scores=iter(sigmoid(weights[0]+feature@weights[1:]))
        transformed[split]=[{**frame,"detections":[{**item,"confidence":max(.001,float(next(scores)))}
                             for item in frame["detections"]]} for frame in pred]
    return transformed,weights.tolist()


def run(mode, settings, original, assets):
    base=Path(settings["base"])
    rows=development_rows(base,pin_plan(base))
    checkpoint=use_d1(settings)
    baseline={split:jsonl(original/f"{split}-tile640.jsonl") for split in rows}
    reference=Path("native")
    reference.mkdir()
    ref=compare(checkpoint,rows,baseline,reference)
    result={"reference":ref}
    if mode=="session":
        threshold=ref["tune"]["confidence"]
        result["by_session"]={name:locked([row for row in rows["dev_check"] if row["session"]==name],
                                          [value for row,value in zip(rows["dev_check"],baseline["dev_check"],strict=True)
                                           if row["session"]==name],threshold)
                              for name in sorted({row["session"] for row in rows["dev_check"]})}
    elif mode=="calibrate":
        transformed,weights=calibrate(rows,baseline)
        path=Path("geometry-score")
        path.mkdir()
        result.update(weights=weights,metrics=compare(checkpoint,rows,transformed,path))
    else:
        alternatives={}
        for name in ("A-N","A-S","A-M","A-P2"):
            if not all((assets/f"{name}-{split}.jsonl").is_file() for split in rows):
                continue
            fused={split:merge(baseline[split],jsonl(assets/f"{name}-{split}.jsonl")) for split in rows}
            run=Path(name)
            run.mkdir()
            alternatives[name]=compare(checkpoint,rows,fused,run)
        if not alternatives:
            raise RuntimeError("No independently verified prediction cache was staged")
        result["alternatives"]=alternatives
    save(Path("evidence.json"),result)


if __name__=="__main__":
    cli=ArgumentParser(description=__doc__)
    cli.add_argument("mode",choices=("calibrate","session","ensemble"))
    for name in ("settings","original","assets"):
        cli.add_argument(name,type=Path)
    args=cli.parse_args()
    from edge_threat_response.p430_workflow import read

    run(args.mode,read(args.settings),args.original,args.assets)
