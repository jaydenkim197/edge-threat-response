"""Measure the pinned D1 on the existing 24-frame Orin development release."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time
from zipfile import ZipFile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("development_archive","checkpoint","output"):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()

    import torch
    from PIL import Image
    from torchvision.ops import nms
    from ultralytics import YOLO

    digest=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    if digest!="212a4b80e44674a3863daf240e127af797ac34f235a6e8356f23936b6348d190" or not torch.cuda.is_available():
        raise RuntimeError("Expected the pinned reference detector and CUDA")
    names=[f"frames/{i:02d}.jpg" for i in range(24)]
    with ZipFile(args.development_archive) as archive:
        if sorted(archive.namelist())!=sorted(["initial.pt",*names]) or hashlib.sha256(
            archive.read("initial.pt")).hexdigest()!="c6e5244f649de9722c956e0c861e98975c4334e08cdd9c0a6a74dd53f0e28d0a":
            raise ValueError("Unexpected approved set of development frames")
        frames=[]
        for name in names:
            with archive.open(name) as source,Image.open(source) as image:
                if image.size!=(1920,1080):
                    raise ValueError("Unexpected frame dimensions")
                frames.append(image.convert("RGB"))
    model=YOLO(args.checkpoint)
    if model.names!={0:"knife"}:
        raise ValueError("Expected a knife-only checkpoint")
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    tiled=[(x,y,x+768,y+640) for y in (0,440) for x in (0,576,1152)]
    roi=[(384,216,1536,864)]

    def measure(frame,mode):
        def predict(images,size):
            return model.predict(images,imgsz=size,batch=len(images),device=0,rect=False,conf=.001,
                                 classes=[0],iou=.7,max_det=100,verbose=False)

        regional=tiled if mode=="tile640" else roi if mode=="full960_roi" else []
        boxes,scores=[],[]
        if mode!="tile640":
            entire=predict([frame],960)[0].boxes
            boxes.extend(entire.xyxy.tolist())
            scores.extend(entire.conf.tolist())
        if regional:
            for result,(x,y,x2,y2) in zip(predict([frame.crop(r) for r in regional],640),regional,strict=True):
                for (a,b,c,d),score in zip(result.boxes.xyxy.tolist(),result.boxes.conf.tolist(),strict=True):
                    if mode=="tile640" and ((x>0 and a<3) or (y>0 and b<3)
                        or (x2<1920 and c>x2-x-3) or (y2<1080 and d>y2-y-3)):
                        continue
                    boxes.append([a+x,b+y,c+x,d+y])
                    scores.append(score)
        if boxes and regional:
            nms(torch.tensor(boxes,dtype=torch.float32),torch.tensor(scores),.55)

    args.output.mkdir(exist_ok=False)
    result={"scope":"development_only_file_inference","checkpoint_sha256":digest,
            "frames":len(frames),"tensorrt_python_available":importlib.util.find_spec("tensorrt") is not None,
            "runtime":str(torch.__version__),"modes":{}}
    for mode in ("full960","tile640","full960_roi"):
        torch.cuda.empty_cache()
        for frame in frames[:4]:
            measure(frame,mode)
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        durations=[]
        for frame in frames:
            start=time.perf_counter()
            measure(frame,mode)
            torch.cuda.synchronize()
            durations.append(time.perf_counter()-start)
        result["modes"][mode]={"p50_ms":1000*statistics.median(durations),
                              "p95_ms":1000*statistics.quantiles(durations,n=100,method="inclusive")[94],
                              "peak_torch_mib":torch.cuda.max_memory_allocated()/2**20}
    (args.output/"result.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__=="__main__":
    main()
