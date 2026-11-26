#!/usr/bin/env bash
# Verify the development release, then run the first queued P2 experiment.
set -euo pipefail
umask 077

if [[ $# != 3 ]]; then
  printf 'Usage: %s <incoming> <python> <locks>\n' "$0" >&2
  exit 2
fi
incoming=$(realpath "$1")
python=$(realpath -s "$2")
locks=$(realpath "$3")
release="$incoming/phase2-code"
base="$incoming/phase2-data"
archive="$incoming/etr-p430-site-development-20261126-v1.tar"
source="$incoming/source-84e3a97.tar"
weights="$incoming/yolo26n.pt"
status="$incoming/status-a3-p2.txt"
gpu_id=2

record() {
  printf '%s %s\n' "$(date -Iseconds)" "$*" | tee "$status.tmp"
  mv -- "$status.tmp" "$status"
}

exec 7>"$locks/p430-phase2-driver.lock"
flock -n 7
trap 'record "FAILED exit=$?"' ERR

record WAITING_FOR_ARCHIVE
until [[ -f "$archive" ]]; do sleep 10; done
printf '%s  %s\n' \
  5795a5bd49414d42da0b8f4e159a8abeae24cc9de6ef61eda4b99493f20b94d3 "$archive" \
  b74fee45fddc4e415a01f914ee8a22a7639a9a8a7392bae45195a75d9bf4b4b6 "$source" \
  fe6cb52e62a6169f097d03e28e67f5b0e7bee7598663c3c49f84011265915a09 "$incoming/p2-worker-20261126-ops-v2.zip" \
  9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef "$weights" | sha256sum -c -

record PREFLIGHT
mkdir "$release"
tar xf "$source" -C "$release"
"$python" -m zipfile -e "$incoming/p2-worker-20261126-ops-v2.zip" "$release/tools"
export PYTHONPATH="$release/src" PYTHONUTF8=1 YOLO_AUTOINSTALL=false
"$python" "$release/tools/stage_p430_site_release.py" --unpack "$archive" "$base"

work="$base/runs/p430-phase2-p2-20261126-v1"
approved="$base/runs/p430-site-20261124-v1"
mkdir "$work"
ln -s "$approved/tiles" "$work/tiles"
cp -- "$approved/plan.json" "$approved/protection.json" "$work/"
ln -s "$weights" "$work/yolo26n.pt"
yaml=$("$python" -c 'import importlib.util,pathlib; import sys; p=pathlib.Path(importlib.util.find_spec("ultralytics").origin); sys.stdout.write(str(p.parent / "cfg/models/26/yolo26-p2.yaml"))')
cp -- "$yaml" "$work/yolo26n-p2.yaml"

"$python" - "$work" "$release" <<'PY'
import sys
from pathlib import Path
from edge_threat_response.p430_workflow import require, save, sha

work, release = map(Path, sys.argv[1:])
plan_sha = sha(work / "plan.json")
require(plan_sha == "8a92eefb8f4bf275d5ace1aae46edb37ad7c6fce02a0484e497fec96deb0a28c",
        "Unexpected development plan")
save(work / "release.json", {"variant": "p2", "seed": 3407, "model": "yolo26n.pt",
     "initial_sha256": sha(work / "yolo26n.pt"), "architecture_sha256": sha(work / "yolo26n-p2.yaml"),
     "plan_sha256": plan_sha, "protection_sha256": sha(work / "protection.json"),
     "runner_sha256": sha(release / "tools/run_p430_site.py"), "base_commit": "84e3a97"})
PY

gpu=$(nvidia-smi -i "$gpu_id" --query-gpu=uuid --format=csv,noheader)
[[ "$gpu" =~ ^GPU-[0-9a-f-]+$ ]]
record WAITING_FOR_GPU
exec 8>"$locks/p430-phase2-one-gpu.lock"
exec 9>"$locks/$gpu.lock"
while true; do
  if flock -n 8 && flock -n 9; then
    active=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
    current=$(nvidia-smi -i "$gpu_id" --query-gpu=uuid,name,memory.total --format=csv,noheader)
    if [[ -z "$active" && "$current" == "$gpu, NVIDIA GeForce RTX 3090, 24576 MiB" ]]; then break; fi
  fi
  flock -u 9
  flock -u 8
  sleep 20
done

export CUDA_VISIBLE_DEVICES="$gpu" YOLO_CONFIG_DIR="$work/yolo" MPLCONFIGDIR="$work/matplotlib"
mkdir -p "$YOLO_CONFIG_DIR/Ultralytics" "$MPLCONFIGDIR"
record "RUNNING gpu=$gpu_id job=p430-phase2-p2-20261126-v1"
"$python" -u "$release/tools/run_p430_site.py" worker "$work" lab2 > "$work/lab2-stdout.log" 2> "$work/lab2-stderr.log"
record COMPLETED
