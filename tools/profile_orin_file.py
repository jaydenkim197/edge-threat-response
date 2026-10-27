"""Bounded, warm-model file profile on Orin; not a camera/event benchmark."""
import argparse
import json
import platform
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import edge_threat_response.runtime as runtime_module
import edge_threat_response.pipeline as pipeline_module

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detect_cli import DetectorConfig, _provenance, build_detector
from edge_threat_response.domain import FrameStatus
from edge_threat_response.media import FramePacket, OpenCVFrameSource
from edge_threat_response.runtime import run_live_pipeline
from edge_threat_response.training import _environment_record, _git_commit, _sha256_file, _write_json
from verify_development_video import require, rows
from verify_orin_file_smoke import HASHES


def resource_sample(torch, elapsed, frame_index):
    mem = {line.split(":")[0]:int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
           if line.startswith(("MemAvailable:","MemTotal:"))}
    status = {line.split(":")[0]:int(line.split()[1]) for line in Path("/proc/self/status").read_text().splitlines()
              if line.startswith(("VmRSS:","VmHWM:"))}
    temperatures = {}
    for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
        try:
            value = int((zone/"temp").read_text())/1000
            if -20<=value<=140:
                temperatures[(zone/"type").read_text().strip()] = value
        except (OSError,ValueError):
            continue
    require(bool(temperatures),"No thermal readings; cannot run guarded profile")
    return {"elapsed_s":elapsed,"frame_index":frame_index,"memory_kib":mem,"process_kib":status,
            "temperatures_c":temperatures,"cuda_allocated_bytes":torch.cuda.memory_allocated(),
            "cuda_reserved_bytes":torch.cuda.memory_reserved(),"cuda_peak_allocated_bytes":torch.cuda.max_memory_allocated()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture","detector-config","pipeline-config","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--seconds",type=float,default=600)
    args = parser.parse_args()
    sources = {"profile":Path(__file__),"runtime":Path(runtime_module.__file__),"pipeline":Path(pipeline_module.__file__)}
    code_sha256 = {name:_sha256_file(path) for name,path in sources.items()}
    require(platform.machine()=="aarch64" and "Orin" in Path("/proc/device-tree/model").read_text(),"Actual Orin required")
    require(1<=args.seconds<=1800 and not args.output.exists(),"Use a bounded duration and fresh output")
    require(_sha256_file(args.fixture)==HASHES["fixture"],"Use the frozen development video")
    config = DetectorConfig.load(args.detector_config)
    require(config.topology=="composite" and len(config.components)==2,"The fixed composite profile requires two components")
    require(all(c.class_map in ({0:"person"},{0:"knife"}) and c.predict_arguments.get("device") in (0,"0")
                and c.predict_arguments.get("imgsz")==640 for c in config.components),"Use fixed canonical maps and CUDA0/640 settings")
    observed = {"person" if c.class_map=={0:"person"} else "knife":_sha256_file(Path(c.weights)) for c in config.components}
    require(observed=={k:HASHES[k] for k in ("person","knife")},"Fixed detector weights/class maps changed")
    import torch
    require(torch.cuda.is_available(),"Do not fall back to CPU")
    detector = build_detector(config)
    warm_start = time.perf_counter()
    warm_frames = 0
    for packet in OpenCVFrameSource(args.fixture):
        require(detector.infer(packet.image).status is FrameStatus.VALID,"Warmup inference failed")
        warm_frames += 1
    torch.cuda.synchronize()
    warm_seconds = time.perf_counter()-warm_start
    require(warm_frames==53,"Warmup input incomplete")
    torch.cuda.reset_peak_memory_stats()
    power_before = subprocess.check_output(["/usr/sbin/nvpmodel","-q"],text=True).strip()
    pipeline = replace(load_pipeline_config(args.pipeline_config),run_id=args.output.name,config_id="bounded-orin-file-profile")
    args.output.mkdir(parents=True)
    samples = []
    started = time.perf_counter()
    def frames():
        index = 0
        next_sample = 0
        while True:
            for packet in OpenCVFrameSource(args.fixture):
                elapsed = time.perf_counter()-started
                if elapsed>=args.seconds:
                    return
                if elapsed>=next_sample:
                    sample = resource_sample(torch,elapsed,index)
                    samples.append(sample)
                    with (args.output/"resources.jsonl").open("a") as handle:
                        handle.write(json.dumps(sample)+"\n")
                    require(max(sample["temperatures_c"].values())<85,"Test guard: sampled temperature reached 85C")
                    require(sample["memory_kib"]["MemAvailable"]>512*1024,"Test guard: available memory below 512MiB")
                    next_sample = elapsed+5
                yield FramePacket(index,index/10,"repeated-train-fixture",packet.image)
                index += 1
    provenance = _provenance(args.fixture,args.detector_config,config)
    provenance["base_pipeline_sha256"] = _sha256_file(args.pipeline_config)
    stream = frames()
    with (args.output/"tegrastats.log").open("w") as log:
        monitor = subprocess.Popen(["tegrastats","--interval","1000"],stdout=log,stderr=subprocess.STDOUT)
        try:
            summary = run_live_pipeline(stream,detector,pipeline,output_dir=args.output/"live-b3",provenance=provenance)
        except Exception as exc:
            _write_json(args.output/"profile.json",{"status":"aborted","error":str(exc),"elapsed_s":time.perf_counter()-started})
            raise
        finally:
            stream.close()
            monitor.terminate()
            monitor.wait(timeout=10)
    elapsed = time.perf_counter()-started
    final = resource_sample(torch,elapsed,summary["frame_count"])
    samples.append(final)
    with (args.output/"resources.jsonl").open("a") as handle:
        handle.write(json.dumps(final)+"\n")
    events = rows(args.output/"live-b3/events.jsonl")
    expected = [i for i in range(summary["frame_count"]) if i%53 in {19,40}]
    require([row["frame_index"] for row in events]==expected,"Repeated input produced unexpected event transitions")
    require(summary["frame_status_counts"]=={"valid":summary["frame_count"]} and summary["action_error_count"]==0,"Runtime error during profile")
    require(summary["snapshot_count"]==len(expected),"Snapshot count mismatch")
    power_after = subprocess.check_output(["/usr/sbin/nvpmodel","-q"],text=True).strip()
    require(power_before==power_after,"Power mode changed during profile")
    require(_provenance(args.fixture,args.detector_config,config)=={k:v for k,v in provenance.items() if k!="base_pipeline_sha256"},"Profile input bytes changed")
    require(code_sha256=={name:_sha256_file(path) for name,path in sources.items()},"Profile source changed during the run")
    result = {"schema_version":1,"status":"completed_bounded_warm_file_profile","git_commit":_git_commit(),
              "code_sha256":code_sha256,
              "environment":_environment_record(),"requested_seconds":args.seconds,"elapsed_s":elapsed,
              "warmup_frames":warm_frames,"warmup_seconds":warm_seconds,"frames":summary["frame_count"],
              "file_processing_fps":summary["frame_count"]/elapsed,"inference_ms":summary["inference_ms"],
              "frame_processing_ms":summary["frame_processing_ms"],"event_count":summary["event_count"],
              "snapshot_count":summary["snapshot_count"],"action_errors":summary["action_error_count"],
              "sample_count":len(samples),"max_sampled_temperature_c":max(max(s["temperatures_c"].values()) for s in samples),
              "first_rss_kib":samples[0]["process_kib"]["VmRSS"],"final_rss_kib":final["process_kib"]["VmRSS"],
              "max_sampled_rss_kib":max(s["process_kib"]["VmRSS"] for s in samples),
              "minimum_sampled_available_kib":min(s["memory_kib"]["MemAvailable"] for s in samples),
              "cuda_peak_allocated_bytes":final["cuda_peak_allocated_bytes"],"provenance":provenance,
              "power_mode_before":power_before,"power_mode_after":power_after,
              "limits":["repeated train still montage, not camera FPS or event accuracy","warmup excluded; sequential file decode/inference/actions/logging included in throughput",
                        "logical frame timestamps differ from elapsed processing time","85C/512MiB are test abort guards, not device specifications",
                        "scalar latency samples and mock-alarm history still grow with run length; not unlimited-memory or 24h stability proof"]}
    _write_json(args.output/"profile.json",result)
    print(json.dumps({k:result[k] for k in ("status","elapsed_s","frames","file_processing_fps","event_count","max_sampled_temperature_c")}))


if __name__=="__main__":
    main()
