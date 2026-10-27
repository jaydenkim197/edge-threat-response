"""Read-only Jetson inventory; excludes network addresses, serials and credentials."""
import argparse
import json
import platform
import re
import subprocess
import warnings
from pathlib import Path


def command(args, timeout=15):
    try:
        result = subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        return {"argv":args,"exit_code":result.returncode,"stdout":result.stdout.strip(),"stderr":result.stderr.strip()}
    except FileNotFoundError:
        return {"argv":args,"status":"not_installed"}
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b""
        return {"argv":args,"status":"bounded_sample_complete","stdout":output.decode(errors="replace") if isinstance(output,bytes) else output}


def read(path):
    item = Path(path)
    return item.read_text().replace("\0"," ").strip() if item.exists() else None


def cuda_smoke():
    """Exercise real CUDA kernels, not only the availability flag."""
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        import torch
        import torchvision
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available")
        with torch.inference_mode():
            matrix = torch.ones((32,32),device="cuda")
            if (matrix@matrix).sum().item()!=32768:
                raise RuntimeError("CUDA matrix result mismatch")
            layer = torch.nn.Conv2d(3,8,3,bias=False).cuda()
            layer.weight.fill_(1)
            output = layer(torch.ones((1,3,8,8),device="cuda"))
            if output.device.type!="cuda" or not torch.all(output==27).item():
                raise RuntimeError("CUDA convolution result mismatch")
            boxes = torch.tensor([[0,0,10,10],[1,1,9,9],[20,20,30,30]],dtype=torch.float32,device="cuda")
            scores = torch.tensor([.9,.8,.7],device="cuda")
            kept = torchvision.ops.nms(boxes,scores,.5)
            if kept.device.type!="cuda" or kept.tolist()!=[0,2]:
                raise RuntimeError("Torchvision CUDA NMS mismatch")
            torch.cuda.synchronize()
        return {"status":"passed_bounded_cuda_kernels","torch":torch.__version__,"torchvision":torchvision.__version__,
                "torch_cuda":torch.version.cuda,"gpu_name":torch.cuda.get_device_name(0),
                "compute_capability":list(torch.cuda.get_device_capability(0)),"compiled_arches":torch.cuda.get_arch_list(),
                "operations":["matrix_multiply","cudnn_convolution","torchvision_nms"],
                "warnings":[str(item.message) for item in captured],"formal_runtime_adopted":False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--cuda-smoke",action="store_true")
    args = parser.parse_args()
    if args.output.exists() or platform.machine()!="aarch64" or not Path("/etc/nv_tegra_release").is_file():
        raise ValueError("Use a fresh output on a Jetson aarch64 device")
    release = read("/etc/nv_tegra_release")
    match = re.search(r"# R(\d+).*REVISION: ([\d.]+)",release)
    observed = match.group(1)+"."+match.group(2) if match else None
    mem = {line.split(":")[0]:line.split(":",1)[1].strip() for line in Path("/proc/meminfo").read_text().splitlines()
           if line.split(":")[0] in {"MemTotal","MemAvailable","SwapTotal"}}
    packages = ["nvidia-l4t-core","nvidia-l4t-bootloader","nvidia-jetpack","cuda-toolkit-13-2",
                "libnvinfer10","python3-libnvinfer","libcudnn9-cuda-13"]
    record = {"schema_version":1,"status":"observed_not_formal_platform_adoption",
              "architecture":platform.machine(),"kernel":platform.release(),"python":platform.python_version(),
              "device_model":read("/proc/device-tree/model"),"device_compatible":read("/proc/device-tree/compatible"),
              "os_release":read("/etc/os-release"),"nv_tegra_release":release,"l4t_release":observed,
              "planned_l4t_release":"39.2.1","matches_planned_l4t":observed=="39.2.1",
              "firmware_bios_version":read("/sys/class/dmi/id/bios_version"),"memory":mem,
              "packages":command(["dpkg-query","-W","-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n",*packages]),
              "storage":command(["lsblk","-J","-o","NAME,SIZE,TYPE,MOUNTPOINTS"]),"root_space":command(["df","-h","/"]),
              "gpu_driver":command(["nvidia-smi","--query-gpu=name,driver_version","--format=csv,noheader"]),
              "cuda_compiler":command(["/usr/local/cuda/bin/nvcc","--version"]),
              "power_mode":command(["/usr/sbin/nvpmodel","-q"]),
              "tegrastats_sample":command(["tegrastats","--interval","1000"],timeout=3),
              "video_device_nodes":[p.name for p in Path("/dev").glob("video*")],
              "limits":["read-only inventory, no power/clock/firmware/OS updates","device-tree name is not a physical module inspection",
                        "package presence is not runtime verification","tegrastats is a short observation, not a benchmark"]}
    if args.cuda_smoke:
        record["cuda_smoke"] = cuda_smoke()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:record[k] for k in ("status","device_model","l4t_release","matches_planned_l4t","memory","video_device_nodes")}))


if __name__=="__main__":
    main()
