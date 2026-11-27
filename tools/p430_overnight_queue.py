"""Poll P430 receipts and run eligible development jobs on one worker per host."""

import argparse
import base64
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from edge_threat_response.p430_queue import alive, process_lock
from edge_threat_response.p430_workflow import now, read, require, save, sha
from p430_followup_actions import site_receipt

FINAL = {"COMPLETED", "SKIPPED", "FAILED"}
SSH = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5"]
ORDER = {"A": 0, "B": 1, "C": 2}


def load(path, default):
    try:
        return read(path) if path.is_file() else default
    except (OSError, ValueError):
        return default


def lookup(obj, dotted):
    for key in dotted.split("."):
        if not isinstance(obj,dict) or key not in obj:
            return None
        obj=obj[key]
    return obj


def wins(candidate, reference):
    if not candidate or not reference:
        return False
    return (candidate["neg"]<=1 and candidate["small"]>=reference["small"]-1
            and candidate["tp"]>=reference["tp"]-2
            and (candidate["tp"]>=reference["tp"]+3 or candidate["small"]>=reference["small"]+2))


def predicate(rule, all_jobs):
    operation, subject, value, *tail=rule
    data=all_jobs.get(subject,{}).get("data",{})
    if operation=="win":
        return wins(data.get("metrics"),all_jobs.get(value,{}).get("data",{}).get("metrics"))
    if operation=="win_any":
        reference=all_jobs.get(value,{}).get("data",{}).get("metrics")
        return any(wins(all_jobs.get(key,{}).get("data",{}).get("metrics"),reference) for key in (subject,*tail))
    observed=lookup(data,value)
    if operation=="exists":
        return observed is not None
    if operation=="equals":
        return observed==tail[0]
    if operation=="atleast":
        return observed is not None and observed>=tail[0]
    raise ValueError(f"Unknown decision rule {operation}")


def decide(job, evidence, settings):
    requires=job.get("after",[])
    states=[evidence.get(dependency,{}).get("status") for dependency in requires]
    if any(state in {"FAILED","SKIPPED"} for state in states):
        return "SKIPPED", "A required experiment did not pass"
    if any(state!="COMPLETED" for state in states):
        return "PENDING", "Waiting for completed prerequisites"
    if any(not predicate(rule,evidence) for rule in job.get("when",[])):
        return "SKIPPED", "Measured execution condition was not met"
    if job.get("approval"):
        approval=Path(settings["approvals"])/job["approval"]
        if not approval.is_file():
            return "PENDING", "Waiting for development approval or on-device inputs"
    model=job.get("parameters",{}).get("model")
    if model and not Path(settings.get("weights",{}).get(model,{}).get("path",".")).is_file():
        return "PENDING", "Waiting for a pinned official checkpoint"
    if job.get("parameters",{}).get("teacher") and not (Path(settings["approvals"])/"A-DISTILL-teacher.pt").is_file():
        return "PENDING", "Waiting for the measured teacher checkpoint"
    return "READY", "All declared prerequisites satisfied"


def imported(job, source):
    path=Path(source["path"])
    if source["kind"]=="site":
        state=load(path/"state.json",{})
        if state.get("status")=="COMPLETED":
            return "COMPLETED",site_receipt(path)
        if state.get("status")=="FAILED":
            return "FAILED",{"reason":state.get("reason","")}
        return ("RUNNING" if state else "PENDING"),{"phase":state.get("phase")}
    if not path.is_file():
        return "PENDING",{}
    report=read(path)
    if "dev_check" not in report:
        return "RUNNING",{}
    mode="tile640" if job["id"]=="A0" else source.get("mode","native")
    point=report["dev_check"][mode]["locked_point"]
    return "COMPLETED", {"metrics":{"small":point["small_tp"],"tp":point["tp"],"neg":point["negative_images_with_fp"],
                         "fp":point["fp"],"confidence":point["confidence"],"ap50":report["dev_check"][mode]["ap50"]},
                         "result_sha256":sha(path),"local_result":str(path)}


def busy(settings):
    node=settings["node"]
    base=Path(settings["base"])
    lock="gpu0-training.lock" if node.startswith("pc") else f"{settings['uuid']}-training.lock"
    if (base.parent/"training"/lock).is_file():
        return True
    entries=subprocess.run(["nvidia-smi","--query-compute-apps=pid,process_name","--format=csv,noheader"],
                           text=True,capture_output=True,timeout=8,check=True).stdout.strip().splitlines()
    if os.name!="nt":
        return bool(entries)
    if not entries:
        return False
    pids=[line.split(",",1)[0].strip() for line in entries]
    require(all(pid.isdigit() for pid in pids),"GPU process ownership could not be checked")
    command=f"Get-Process -Id {','.join(pids)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"
    names=subprocess.run(["powershell","-NoProfile","-Command",command],text=True,capture_output=True,timeout=8).stdout.splitlines()
    known={"dwm","shellhost","crossdeviceresume","explorer","startmenuexperiencehost","searchhost","msedgewebview2",
           "phoneexperiencehost","textinputhost","movavisuite","shellexperiencehost","copilotapp","copilotapphost",
           "msedge","clipdown","applicationframehost","systemsettings"}
    return any(name.strip().lower() not in known for name in names)


@contextmanager
def reserve(job,settings):
    with ExitStack() as stack:
        if job.get("gpu"):
            if os.name!="nt":
                locks=Path(settings["locks"])
                stack.enter_context(process_lock(locks/"p430-phase2-one-gpu.lock"))
                stack.enter_context(process_lock(locks/f"{settings['uuid']}.lock"))
            visible=subprocess.check_output(["nvidia-smi","-i",str(settings["gpu_id"]),"--query-gpu=uuid",
                                             "--format=csv,noheader"],text=True,timeout=8).strip()
            if visible!=settings["uuid"] or busy(settings):
                raise BlockingIOError("GPU unavailable or occupied")
        yield


def persist(root,settings,states):
    save(root/"status.json",{"node":settings["node"],"time":now(),"jobs":states})


def action(root, job, settings, evidence, states):
    previous=states.get(job["id"],{})
    number=previous.get("attempt",0)+1
    attempt=root/"jobs"/job["id"]/f"attempt-{number:02d}"
    attempt.mkdir(parents=True,exist_ok=False)
    task=attempt/"task.json"
    save(task,{"job":job,"settings":settings,"evidence":evidence})
    env={**os.environ,"PYTHONUTF8":"1","YOLO_AUTOINSTALL":"false","KMP_DUPLICATE_LIB_OK":"TRUE",
         "CUDA_VISIBLE_DEVICES":settings["uuid"] if job.get("gpu") else "",
         "YOLO_CONFIG_DIR":str(attempt/"yolo")}
    (attempt/"yolo/Ultralytics").mkdir(parents=True)
    command=[sys.executable,"-u",str(Path(__file__).with_name("p430_followup_actions.py")),str(task),str(attempt)]
    with (attempt/"stdout.log").open("xb") as stdout,(attempt/"stderr.log").open("xb") as stderr:
        child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,env=env)
        record={"status":"RUNNING","attempt":number,"pid":child.pid,"path":str(attempt),"time":now()}
        states[job["id"]]=record
        persist(root,settings,states)
        code=child.wait()
    save(attempt/"exit.json",{"code":code,"time":now()})
    result=attempt/"result.json"
    if code==0 and result.is_file():
        record.update(status="COMPLETED",data=read(result),result_sha256=sha(result))
    else:
        record.update(status="FAILED",reason=f"Exit {code}; see the attempt logs")
    persist(root,settings,states)


def recover(record):
    attempt=Path(record["path"])
    result=attempt/"result.json"
    exit_record=load(attempt/"exit.json",{})
    if exit_record.get("code")==0 and result.is_file():
        return {**record,"status":"COMPLETED","data":read(result),"result_sha256":sha(result)}
    if alive(record["pid"]):
        return record
    if not exit_record and record["attempt"]==1 and not (attempt/"work.json").is_file():
        return {**record,"status":"PENDING","reason":"Interrupted before the training run was created; retry once"}
    return {**record,"status":"FAILED","reason":"Interrupted or failed; preserve artifacts and partial weights"}


def worker(root):
    settings=read(root/"settings.json")
    with process_lock(root/"worker.lock"):
        states=load(root/"status.json",{}).get("jobs",{})
        jobs=[]
        while True:
            registry=load(root/"registry.json",None)
            if registry is not None:
                jobs=sorted((job for job in registry["jobs"] if job["node"]==settings["node"]),
                            key=lambda job:ORDER[job["track"]])
            shared=load(root/"shared.json",{})
            for job in jobs:
                key=job["id"]
                prior=states.get(key,{})
                if prior.get("status") in FINAL:
                    continue
                if job["kind"]=="existing":
                    try:
                        status,data=imported(job,settings["sources"][key])
                        states[key]={"status":status,"data":data}
                    except (OSError,ValueError,KeyError) as error:
                        states[key]={"status":"PENDING","reason":str(error)}
                elif prior.get("status")=="RUNNING":
                    states[key]=recover(prior)
            for job in jobs:
                key=job["id"]
                prior=states.get(key,{})
                if job["kind"]=="existing" or prior.get("status") in FINAL|{"RUNNING"}:
                    continue
                status,reason=decide(job,{**shared,**states},settings)
                states[key]={**prior,"status":status,"reason":reason}
            persist(root,settings,states)
            if any(states.get(job["id"],{}).get("status")=="RUNNING" and job["kind"]!="existing" for job in jobs):
                time.sleep(15)
                continue
            if not (root/"pause.request").exists():
                for job in jobs:
                    key=job["id"]
                    if states.get(key,{}).get("status")!="READY":
                        continue
                    try:
                        with reserve(job,settings):
                            action(root,job,settings,{**shared,**states},states)
                        break
                    except (BlockingIOError,OSError,subprocess.SubprocessError) as error:
                        states[key]["reason"]=str(error)
                        persist(root,settings,states)
            time.sleep(15)


def sync(root):
    options=read(root/"mirror.json")
    snapshot=root/"shared.json"
    nodes=options["nodes"]
    remote=options["remote_directory"]
    require(remote.replace("-","").isalnum() and all(node.replace("-","").isalnum() for node in nodes),"Invalid mirror path")
    with process_lock(root/"mirror.lock"), tempfile.TemporaryDirectory(dir=root) as temp:
        states=load(snapshot,{})
        while True:
            for node in nodes:
                local=Path(temp)/f"{node}.json"
                try:
                    subprocess.run(["scp","-q",*SSH,f"{node}:{remote}/status.json",str(local)],
                                   timeout=18,check=True,capture_output=True)
                    payload=read(local)
                    states.update({key:{**value,"host":node} for key,value in payload["jobs"].items()})
                except (subprocess.SubprocessError,ValueError,OSError):
                    continue
            save(snapshot,states)
            for node,platform in nodes.items():
                try:
                    subprocess.run(["scp","-q",*SSH,str(snapshot),f"{node}:{remote}/shared.part"],
                                   timeout=18,check=True,capture_output=True)
                    if platform=="windows":
                        script=(f'$d=Join-Path $env:USERPROFILE "{remote}"; '
                                '$a=Join-Path $d "shared.part"; $b=Join-Path $d "shared.json"; '
                                '$previous=Join-Path $d "shared.previous.json"; '
                                'if ([IO.File]::Exists($b)) {[IO.File]::Replace($a,$b,$previous)} else {[IO.File]::Move($a,$b)}')
                        encoded=base64.b64encode(script.encode("utf-16le")).decode()
                        move=["powershell","-NoProfile","-EncodedCommand",encoded]
                    else:
                        move=["mv",f"{remote}/shared.part",f"{remote}/shared.json"]
                    subprocess.run(["ssh",*SSH,node,*move],timeout=15,check=True,capture_output=True)
                except (subprocess.SubprocessError,OSError):
                    continue
            if options.get("ensemble_approval"):
                try:
                    deliver_ensemble(root,options,states)
                except (subprocess.SubprocessError,OSError,ValueError,KeyError):
                    pass  # The next mirror round retries incomplete asset delivery.
            time.sleep(20)


def deliver_ensemble(root,options,states):
    ids=("A-N","A-S","A-M","A-P2")
    if any(states.get(key,{}).get("status") not in FINAL for key in ids):
        return
    target=f"pc13:{options['remote_directory']}"
    assets=root/"ensemble-cache"
    assets.mkdir(exist_ok=True)
    if (assets/"delivered.json").is_file():
        return
    verified=[]
    for key in ids:
        state=states[key]
        if state["status"]!="COMPLETED":
            continue
        data=state["data"]
        host=state["host"]
        if host not in options["nodes"]:
            continue
        source=data["local_result"].replace("\\","/")
        receipt=assets/f"{key}.json"
        subprocess.run(["scp","-q",*SSH,f"{host}:{source}",str(receipt)],timeout=20,check=True,capture_output=True)
        require(sha(receipt)==data["result_sha256"],"Remote evaluation receipt differs")
        tile=read(receipt)["result"]["tile640"]
        name=tile["selected_checkpoint"]
        records={"tune":next(item for item in tile["tune"] if item["checkpoint"]==name),"dev_check":tile["dev_check"][name]}
        filenames = {
            "tune": f"tune-tile640-{Path(name).stem}.jsonl",
            "dev_check": f"dev-tile640-{name}.jsonl",
        }
        for partition,record in records.items():
            cache=assets/f"{key}-{partition}.jsonl"
            original=f"{source.rsplit('/',1)[0]}/{filenames[partition]}"
            subprocess.run(["scp","-q",*SSH,f"{host}:{original}",str(cache)],timeout=50,check=True,capture_output=True)
            require(sha(cache)==record["predictions_sha256"],"Remote prediction cache differs")
            subprocess.run(["scp","-q",*SSH,str(cache),f"{target}/assets/{cache.name}"],timeout=50,check=True,capture_output=True)
        verified.append(key)
    if verified:
        approval=Path(options["ensemble_approval"])
        subprocess.run(["scp","-q",*SSH,str(approval),f"{target}/approvals/A-ENSEMBLE.json"],
                       timeout=20,check=True,capture_output=True)
        save(assets/"delivered.json",{"jobs":verified,"time":now()})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("worker","sync"))
    parser.add_argument("root",type=Path)
    args=parser.parse_args()
    (worker if args.mode=="worker" else sync)(args.root.resolve())
