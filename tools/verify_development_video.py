"""Real-weight PC video integration on train-derived fixtures, never an event benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detect_cli import DetectorConfig, _provenance, build_detector
from edge_threat_response.detector import CallableBackend
from edge_threat_response.domain import FrameStatus, SpatialPolicy
from edge_threat_response.media import OpenCVFrameSource
from edge_threat_response.replay import write_jsonl
from edge_threat_response.replay_cli import main as replay_main
from edge_threat_response.runtime import run_detection_stream, run_live_pipeline
from edge_threat_response.spatial import associate_person_knives
from edge_threat_response.training import TrainingConfig, _environment_record, _git_commit, _sha256_file, _write_json, validate_training_approval


SEGMENTS = [("blank",4),("person_negative",4),("knife_only",4),("blank",6),
            ("associated",8),("blank",6),("associated",1),("blank",6),("associated",8),("blank",6)]
EXPECTED_EVENTS = {"B0":[8,18,32,39],"B1":[9,19,40],"B2":[18,32,39],"B3":[19,40]}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canvas(image, index):
    import cv2
    import numpy as np
    result = np.zeros((640,640,3),dtype=np.uint8)
    if image is not None:
        height,width = image.shape[:2]
        scale = min(640/width,600/height)
        width,height = round(width*scale),round(height*scale)
        resized = cv2.resize(image,(width,height))
        x,y = (640-width)//2,(600-height)//2
        result[y:y+height,x:x+width] = resized
    # Distinct frames make wrong-frame snapshot binding detectable, even with repeated stills.
    cv2.putText(result,f"frame {index:03d}",(8,628),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
    return result


def verify_snapshots(directory, video):
    import cv2
    events = rows(directory / "events.jsonl")
    frames = {packet.frame_index:packet.image for packet in OpenCVFrameSource(video)}
    evidence = []
    for event in events:
        require(event["snapshot_status"]=="captured","Snapshot was not captured")
        path = Path(event["snapshot_path"])
        require(path.resolve().parent==(directory/"snapshots").resolve(),"Snapshot escaped its output")
        ok,encoded = cv2.imencode(".jpg",frames[event["frame_index"]])
        require(ok and path.read_bytes()==encoded.tobytes(),"Snapshot does not match the event's decoded frame")
        evidence.append({"frame_index":event["frame_index"],"sha256":_sha256_file(path)})
    require(len(events)==len(list((directory/"snapshots").glob("*.jpg"))),"Orphan/duplicate snapshots")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared","person-weights","knife-weights","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--expected-person-sha256",required=True)
    parser.add_argument("--expected-knife-sha256",required=True)
    parser.add_argument("--device",default="0")
    args = parser.parse_args()
    require(not args.output.exists(),"Use a fresh integration output; preserve previous evidence")
    for path,digest in ((args.person_weights,args.expected_person_sha256),(args.knife_weights,args.expected_knife_sha256)):
        require(path.is_file() and _sha256_file(path)==digest,"Missing or changed local weights; do not auto-download")
    config = TrainingConfig.load(args.prepared/"training.json")
    require(config.recipe_id=="DEV-SOHAS","This fixture requires the authorized SOHAS development subset")
    approval = validate_training_approval(args.prepared/"training.json",config,args.prepared/"data.yaml",
                                         args.prepared/"DEV-manifest.jsonl",args.prepared/"development-authorization.json")
    manifest_hash = _sha256_file(args.prepared/"DEV-manifest.jsonl")
    require(args.output.resolve()!=args.prepared.resolve() and not args.output.resolve().is_relative_to(args.prepared.resolve()),
            "Output must be separate from prepared inputs")
    # Filter before opening images. Val/test are integrity-hashed by approval validation only.
    train = [row for row in rows(args.prepared/"DEV-manifest.jsonl") if row["split"]=="train"]
    args.output.mkdir(parents=True)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG",":4096:8")
    import cv2
    import torch
    torch.use_deterministic_algorithms(True)
    detector_payload = {"schema_version":1,"topology":"composite","components":[
        {"component_id":name,"weights":path.resolve().as_posix(),"class_map":{"0":label},
         "predict_arguments":{"imgsz":640,"device":args.device,"conf":confidence,"classes":[0],"iou":.7,"half":False}}
        for name,path,label,confidence in (("coco-person",args.person_weights,"person",.5),("custom-knife",args.knife_weights,"knife",.25))]}
    detector_path = args.output/"detector.json"
    _write_json(detector_path,detector_payload)
    detector_config = DetectorConfig.load(detector_path)
    detector = build_detector(detector_config)
    require(detector.components[0].backend._get_model().names.get(0)=="person","Person class0 mismatch")
    require(detector.components[1].backend._get_model().names=={0:"knife"},"Knife class0 mismatch")
    candidates,probe = {},[]
    for row in train:
        image = cv2.imread(row["image"])
        require(image is not None,"Training image decode failed")
        inference = detector.infer(canvas(image,0))
        require(inference.status is FrameStatus.VALID,"Fixture probe detector error: "+str(inference.error))
        people = tuple(d for d in inference.detections if d.label=="person")
        knives = tuple(d for d in inference.detections if d.label=="knife")
        associations = associate_person_knives(people,knives,policy=SpatialPolicy.EXPANDED_BBOX_ONLY,expanded_person_ratio=.25)
        kind = ("associated" if row["knife_count"] and any(a.associated for a in associations)
                else "knife_only" if row["knife_count"] and knives and not people
                else "person_negative" if row["knife_count"]==0 and people and not knives else None)
        score = min(max((d.confidence for d in people),default=1),max((d.confidence for d in knives),default=1))
        probe.append({"image_sha256":row["image_sha256"],"kind":kind,"score":score})
        if kind and (kind not in candidates or score>candidates[kind][0]):
            candidates[kind] = (score,row,image)
    write_jsonl(args.output/"fixture-probe.jsonl",probe)
    require(set(candidates)=={"associated","knife_only","person_negative"},"Could not obtain all fixture categories at fixed thresholds")
    source_images = {kind:item[2] for kind,item in candidates.items()}
    selection = {kind:{"image_sha256":item[1]["image_sha256"],"source_group":item[1]["source_group"],"split":"train","probe_score":item[0]}
                 for kind,item in candidates.items()}
    video = args.output/"train-derived-fixture.avi"
    writer = cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"FFV1"),10,(640,640))
    require(writer.isOpened(),"FFV1 lossless AVI writer unavailable")
    frame_recipe = []
    try:
        for kind,count in SEGMENTS:
            for _ in range(count):
                index = len(frame_recipe)
                image = canvas(source_images.get(kind),index)
                writer.write(image)
                frame_recipe.append({"frame_index":index,"kind":kind,"decoded_pixels_sha256":hashlib.sha256(image.tobytes()).hexdigest()})
    finally:
        writer.release()
    packets = list(OpenCVFrameSource(video,source_id="train-derived-integration"))
    require(len(packets)==53,"Decoded video frame count mismatch")
    for packet,recipe in zip(packets,frame_recipe):
        require(hashlib.sha256(packet.image.tobytes()).hexdigest()==recipe["decoded_pixels_sha256"],"Video was not lossless")
        require(abs(packet.timestamp_s-packet.frame_index/10)<1e-6,"Video timeline mismatch")
    write_jsonl(args.output/"frame-recipe.jsonl",frame_recipe)
    pipeline_path = args.output/"pipeline.json"
    _write_json(pipeline_path,{"schema_version":2,"config_id":"pc-video-integration-development-only","run_id":args.output.name,
                              "model_version":"person:"+args.expected_person_sha256+";knife:"+args.expected_knife_sha256,
                              "mode":"B3","confidence":{"person":.5,"knife":.25},
                              "spatial":{"policy":"expanded_bbox_only","expanded_person_ratio":.25},
                              "temporal":{"k":2,"n":3},"state_machine":{"rearm_clear_frames":2}})
    pipeline = load_pipeline_config(pipeline_path)
    provenance = {**_provenance(video,detector_path,detector_config),"pipeline_config_sha256":_sha256_file(pipeline_path)}
    detection_dir = args.output/"detection"
    detection_summary = run_detection_stream(packets,detector,output_dir=detection_dir,provenance=provenance)
    require(detection_summary["frame_status_counts"]=={"valid":53},"Video detection failure")
    require(replay_main(["--input",str(detection_dir/"detections.jsonl"),"--config",str(pipeline_path),"--output-dir",str(args.output/"replay")])==0,"Replay CLI failed")
    replay = json.loads((args.output/"replay/summary.json").read_text())
    for result in replay["runs"]:
        require(result["input_sha256"]==detection_summary["detections_sha256"],"Ablation input mismatch")
        require(result["event_frame_indices"]==EXPECTED_EVENTS[result["mode"]],"Unexpected fixture events: "+json.dumps(result))
        require(result["action_error_count"]==0,"Replay action error")
    live_dir = args.output/"live-b3"
    live = run_live_pipeline(packets,detector,pipeline,output_dir=live_dir,provenance=provenance)
    require(live["detections_sha256"]==detection_summary["detections_sha256"],"Fresh live inference differs from detection-only inference")
    require([r["frame_index"] for r in rows(live_dir/"events.jsonl")]==EXPECTED_EVENTS["B3"],"Live/replay event mismatch")
    snapshots = {"live":verify_snapshots(live_dir,video)}
    require(live["event_count"]==2 and live["snapshot_count"]==2 and live["action_error_count"]==0,"Live event/action/snapshot mismatch")
    states = {r["state_after"] for r in rows(live_dir/"decisions.jsonl")}
    require(states=={"CLEAR","CANDIDATE","CONFIRMED","COOLDOWN"},"Four-state coverage incomplete")
    faults = {}
    knife = detector.components[1]
    original_backend = knife.backend
    for name,failed in (("single-error",{21}),("double-error",{21,22})):
        calls = [0]
        def faulty_predict(image):
            index = calls[0]
            calls[0] += 1
            if index in failed:
                raise RuntimeError("injected required knife component failure")
            return original_backend.predict(image)
        knife.backend = CallableBackend(faulty_predict)
        fault_dir = args.output/name
        try:
            summary = run_live_pipeline(packets,detector,pipeline,output_dir=fault_dir,provenance={**provenance,"injected_error_frames":sorted(failed)})
        finally:
            knife.backend = original_backend
        predictions = rows(fault_dir/"detections.jsonl")
        decisions = rows(fault_dir/"decisions.jsonl")
        require([r["frame_index"] for r in predictions if r["status"]=="detector_error"]==sorted(failed),"Fault injection mismatch")
        require(all(not predictions[i]["detections"] for i in failed),"Required-component failure leaked partial detections")
        require(decisions[21]["state_after"]=="CONFIRMED","K-of-N did not tolerate one error sample")
        require(decisions[22]["state_after"]==("COOLDOWN" if len(failed)==2 else "CONFIRMED"),"Consecutive-error transition mismatch")
        require([r["frame_index"] for r in rows(fault_dir/"events.jsonl")]==EXPECTED_EVENTS["B3"],"Fault caused duplicate event or failed rearm")
        require(summary["action_error_count"]==0,"Fault test action error")
        snapshots[name] = verify_snapshots(fault_dir,video)
        faults[name] = {"injected_error_frames":sorted(failed),"frame_status_counts":summary["frame_status_counts"],"event_count":summary["event_count"]}
    require(manifest_hash==_sha256_file(args.prepared/"DEV-manifest.jsonl"),"Prepared manifest changed")
    for path,digest in ((args.person_weights,args.expected_person_sha256),(args.knife_weights,args.expected_knife_sha256)):
        require(_sha256_file(path)==digest,"Checkpoint changed during integration")
    record = {"schema_version":1,"status":"passed_pc_integration_not_benchmark","git_commit":_git_commit(),
              "script_sha256":_sha256_file(Path(__file__)),"environment":_environment_record(),"device":args.device,
              "prepared_manifest_sha256":manifest_hash,"training_scope":approval["scope"],"reserved_test_used":False,
              "fixture":{"kind":"train-derived still montage with unique frame markers","codec":"FFV1","fps":10,"frames":53,
                         "video_sha256":_sha256_file(video),"selection":selection,"segments":SEGMENTS},
              "weight_sha256":{"person":args.expected_person_sha256,"knife":args.expected_knife_sha256},
              "detection":{"frames":detection_summary["frame_count"],"statuses":detection_summary["frame_status_counts"],
                           "count":detection_summary["detection_count"],"sha256":detection_summary["detections_sha256"]},
              "replay":{r["mode"]:{"events":r["event_frame_indices"],"input_sha256":r["input_sha256"],"action_errors":r["action_error_count"]} for r in replay["runs"]},
              "live_b3":{"events":EXPECTED_EVENTS["B3"],"snapshots":live["snapshot_count"],"action_errors":live["action_error_count"],"states":sorted(states)},
              "snapshot_frame_equality":snapshots,"fault_injection":faults,
              "limits":["selected train fixtures test wiring, not detection/event accuracy","assembled still frames do not establish real motion robustness",
                        "mock alarm only, no GPIO/camera/Orin verification","development confidence/geometry/K/N are not frozen research parameters"]}
    _write_json(args.output/"integration.json",record)
    print(json.dumps({"status":record["status"],"events":{k:v["events"] for k,v in record["replay"].items()},"snapshots":live["snapshot_count"]}))


if __name__=="__main__":
    main()
