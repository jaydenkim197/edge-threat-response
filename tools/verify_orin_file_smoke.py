"""Repeat the frozen PC file fixture on an actual Orin; no camera/GPIO or benchmark."""
import argparse
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

from edge_threat_response.training import _environment_record, _git_commit, _sha256_file, _write_json
from edge_threat_response.replay_cli import main as replay_main
from verify_development_video import EXPECTED_EVENTS, require, rows, verify_snapshots


HASHES = {"person":"9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef",
          "knife":"d8eff85efff890041d67f9aea80d3d0d7a9530312eb7c2da2baace5e3840c043",
          "fixture":"b16a569242f37e771f268a6b3d9b1e0ad3c9f98daee85c51d22d0461d2141e6e"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("person","knife","fixture","inventory","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--offline-netns",action="store_true",help="Require a private namespace with only loopback and no external IPv4 route")
    args = parser.parse_args()
    isolation = None
    if args.offline_netns:
        interfaces = [name for _,name in socket.if_nameindex()]
        require(interfaces==["lo"],"Offline test must run in an isolated network namespace")
        try:
            with socket.create_connection(("192.0.2.1",443),timeout=1):
                raise RuntimeError("Unexpected route out of offline namespace")
        except OSError as exc:
            require(exc.errno==101,"Expected ENETUNREACH from the kernel, not a remote timeout")
            isolation = {"scope":"kernel_network_namespace","interfaces":interfaces,"connect_errno":exc.errno,
                         "namespace":os.readlink("/proc/self/ns/net"),"host_network_modified":False}
    require(platform.machine()=="aarch64" and "Orin" in Path("/proc/device-tree/model").read_text(),"Actual Jetson Orin required")
    require(not args.output.exists(),"Use a fresh output and preserve prior runs")
    for name,digest in HASHES.items():
        require(_sha256_file(getattr(args,name))==digest,"Frozen fixture/weight hash mismatch: "+name)
    inventory = json.loads(args.inventory.read_text())
    require(inventory.get("cuda_smoke",{}).get("status")=="passed_bounded_cuda_kernels","First pass the actual CUDA kernel smoke")
    import torch
    require(torch.cuda.is_available(),"Actual CUDA unavailable; do not fall back to CPU")
    require(torch.__version__==inventory["cuda_smoke"]["torch"],"Runtime changed after kernel verification")
    from ultralytics import YOLO
    require(YOLO(str(args.person)).names.get(0)=="person","Person class0 mismatch")
    require(YOLO(str(args.knife)).names=={0:"knife"},"Knife class0 mismatch")
    args.output.mkdir(parents=True)
    detector_path,pipeline_path = args.output/"detector.json",args.output/"pipeline.json"
    _write_json(detector_path,{"schema_version":1,"topology":"composite","components":[
        {"component_id":name,"weights":path.resolve().as_posix(),"class_map":{"0":label},
         "predict_arguments":{"imgsz":640,"device":0,"conf":confidence,"classes":[0],"iou":.7,"half":False}}
        for name,path,label,confidence in (("coco-person",args.person,"person",.5),("custom-knife",args.knife,"knife",.25))]})
    _write_json(pipeline_path,{"schema_version":2,"config_id":"experimental-orin-file-smoke","run_id":args.output.name,
                              "model_version":"person:"+HASHES["person"]+";knife:"+HASHES["knife"],"mode":"B3",
                              "confidence":{"person":.5,"knife":.25},"spatial":{"policy":"expanded_bbox_only","expanded_person_ratio":.25},
                              "temporal":{"k":2,"n":3},"state_machine":{"rearm_clear_frames":2}})
    live = args.output/"live-b3"
    cli = [str(Path(sys.executable).with_name("etr-run")),"--input",str(args.fixture),"--source-id","train-derived-integration",
           "--detector-config",str(detector_path),"--pipeline-config",str(pipeline_path),"--output-dir",str(live)]
    env = dict(os.environ,PYTHONPATH=str(Path("src").resolve()),CUBLAS_WORKSPACE_CONFIG=":4096:8")
    with (args.output/"cli.log").open("w") as log:
        result = subprocess.run(cli,env=env,stdout=log,stderr=subprocess.STDOUT)
    require(result.returncode==0,"etr-run failed; inspect cli.log")
    summary = json.loads((live/"summary.json").read_text())
    require(summary["frame_count"]==53 and summary["frame_status_counts"]=={"valid":53},"Video frames failed")
    require(summary["event_count"]==summary["snapshot_count"]==2 and summary["action_error_count"]==0,"B3 action mismatch")
    require([r["frame_index"] for r in rows(live/"events.jsonl")]==EXPECTED_EVENTS["B3"],"B3 fixture transition mismatch")
    snapshots = verify_snapshots(live,args.fixture)
    require(replay_main(["--input",str(live/"detections.jsonl"),"--config",str(pipeline_path),"--output-dir",str(args.output/"replay")])==0,"Replay failed")
    replay = json.loads((args.output/"replay/summary.json").read_text())["runs"]
    for run in replay:
        require(run["input_sha256"]==summary["detections_sha256"] and run["event_frame_indices"]==EXPECTED_EVENTS[run["mode"]]
                and run["action_error_count"]==0,"Same-input ablation fixture mismatch")
    for name,digest in HASHES.items():
        require(_sha256_file(getattr(args,name))==digest,"Input changed during execution")
    record = {"schema_version":1,"status":"passed_orin_file_smoke_experimental_platform","git_commit":_git_commit(),
              "script_sha256":_sha256_file(Path(__file__)),"environment":_environment_record(),"artifact_sha256":HASHES,
              "inventory_sha256":_sha256_file(args.inventory),"l4t_release":inventory["l4t_release"],
              "matches_planned_l4t":inventory["matches_planned_l4t"],"formal_platform_or_runtime_adopted":False,
              "cuda_warnings":inventory["cuda_smoke"]["warnings"],"cli_exit_code":result.returncode,
              "network_isolation":isolation,
              "frames":summary["frame_count"],"detections":summary["detection_count"],"detections_sha256":summary["detections_sha256"],
              "snapshots":snapshots,"replay":{r["mode"]:{"events":r["event_frame_indices"],"input_sha256":r["input_sha256"]} for r in replay},
              "limits":["frozen train-derived still montage, not independent event evaluation","no camera/GPIO/TensorRT/endurance verification; isolated-netns test is not physical link recovery",
                        "installed platform differs from the project plan","framework versions differ from PC13; no speed or accuracy comparison"]}
    _write_json(args.output/"verification.json",record)
    print(json.dumps({"status":record["status"],"frames":record["frames"],"events":{k:v["events"] for k,v in record["replay"].items()},"snapshots":len(snapshots)}))


if __name__=="__main__":
    main()
