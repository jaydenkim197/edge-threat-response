"""Bounded CCTV inference-path diagnosis; no training or frozen-result edits."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import csv,hashlib,json,sys
import cv2,numpy as np,torch
from PIL import Image
from ultralytics import YOLO
from ultralytics.utils import ops
from ultralytics.utils.metrics import box_iou
from ultralytics.utils import LOGGER
import logging
LOGGER.setLevel(logging.ERROR)

ROOT=Path(r'C:\Class6\edge-threat-response')
SOURCE=Path(r'C:\Class6\etr-worktrees\s1-20261108-run')
RUN=ROOT/'runs/s1-comparison-20261108-v1'
OUT=ROOT/'data/work/cctv-diagnostics-20261108-v2'
sys.path.insert(0,str(SOURCE/'src'))
from edge_threat_response.training import _sha256_file,_write_json,gpu_training_lock
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.detector_comparison import POLICY

load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
read_rows=lambda p:[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
write_rows=lambda p,rows:p.write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
truth_path=Path(load(RUN/'suite.json')['datasets']['us-mock-reviewed']['truth'])
truth=load(truth_path)
protocol=load(RUN/'predict/models.json')
cases=[x for x in protocol['cases'] if x['id'] in ['raw-m1-n-640','raw-m2-n-640','raw-s1-n-640']]
assert len(cases)==3
OUT.mkdir(exist_ok=False,parents=True)
(OUT/'predictions').mkdir();(OUT/'network-inputs').mkdir()
state={'status':'running','source_commit':'ebc7f20924aae8fedf66d227979e6dea5ad266d5',
 'worker_sha256':_sha256_file(Path(__file__)),'truth_sha256':_sha256_file(truth_path),
 'frozen_models_sha256':_sha256_file(RUN/'predict/models.json'),'started_utc':datetime.now(timezone.utc).isoformat(),
 'training_started':False,'final_detector_selected':False,'roi_uses_ground_truth':True}
def record(**fields):
 state.update(fields,updated_utc=datetime.now(timezone.utc).isoformat());_write_json(OUT/'state.json',state)
def report_error(kind,error,traceback):
 record(status='failed',error=f'{kind.__name__}: {error}')
 sys.__excepthook__(kind,error,traceback)
sys.excepthook=report_error
discarded_zero_area=[]

def raw_arrays(result):
 boxes=np.array(result.boxes.xyxy.cpu(),dtype=float).reshape(-1,4)
 scores=np.array(result.boxes.conf.cpu(),dtype=float);classes=np.array(result.boxes.cls.cpu(),dtype=int)
 assert np.isfinite(boxes).all() and np.isfinite(scores).all()
 valid=(boxes[:,2]>boxes[:,0]) & (boxes[:,3]>boxes[:,1])
 for b,s in zip(boxes[~valid],scores[~valid]):
  discarded_zero_area.append({'model':state.get('active'),'phase':state.get('phase'),
      'bbox_xyxy':b.tolist(),'confidence':float(s)})
 return boxes[valid],scores[valid],classes[valid]

def frame(image,boxes,scores):
 return {'source_id':image['source_id'],'frame_index':image['frame_index'],'timestamp_s':0,'status':'valid',
   'detections':[{'label':'knife','confidence':float(s),'bbox_xyxy':[float(v) for v in b]} for b,s in zip(boxes,scores)]}

def overlap_numpy(a,b):
 a=np.asarray(a,dtype=float).reshape(-1,4);b=np.asarray(b,dtype=float).reshape(-1,4)
 inter=np.maximum(0,np.minimum(a[:,None,2:],b[None,:,2:])-np.maximum(a[:,None,:2],b[None,:,:2])).prod(2)
 denom=(a[:,2:]-a[:,:2]).prod(1)[:,None]+(b[:,2:]-b[:,:2]).prod(1)[None,:]-inter
 return np.divide(inter,denom,out=np.zeros_like(inter),where=denom>0)

def independent_counts(t,preds,confidence=.25,overlap=.5):
 index={(x['source_id'],x['frame_index']):x for x in preds};total=Counter(tp=0,fp=0,fn=0)
 for im in t['images']:
  ds=[d for d in index[(im['source_id'],im['frame_index'])]['detections'] if d['confidence']>=confidence]
  ds.sort(key=lambda x:-x['confidence']);unused=set(range(len(im['knife_boxes_xyxy'])))
  matrix=overlap_numpy([x['bbox_xyxy'] for x in ds],im['knife_boxes_xyxy'])
  for n,d in enumerate(ds):
   if unused:
    best=max(sorted(unused),key=lambda i:matrix[n,i])
    if matrix[n,best]>=overlap:unused.remove(best);total['tp']+=1;continue
   total['fp']+=1
  total['fn']+=len(unused)
 return dict(total)

def predict(model,image,size):
 return model.predict(image,device=0,imgsz=size,batch=1,half=False,rect=False,conf=.001,
  classes=[0],iou=.7,max_det=300,nms=None,verbose=False)[0]

torch.manual_seed(20261104);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.set_grad_enabled(False)
oracle=[frame(im,im['knife_boxes_xyxy'],[1.]*len(im['knife_boxes_xyxy'])) for im in truth['images']]
oracle_metrics,_=evaluate_boxes(truth,oracle,POLICY)
assert {k:oracle_metrics['counts'][k] for k in ['tp','fp','fn']}==independent_counts(truth,oracle)=={'tp':31,'fp':0,'fn':0}
audit=[];metrics=[];gt_diagnostics=[];controls=[]
inputs={str(truth_path):_sha256_file(truth_path),str(RUN/'predict/models.json'):_sha256_file(RUN/'predict/models.json')}
with gpu_training_lock(ROOT/'runs/training/gpu0-training.lock',owner='cctv-inference-path-diagnosis'):
 for ci,case in enumerate(cases):
  name=case['id'];record(active=name,phase='direct_640')
  assert _sha256_file(Path(case['checkpoint']))==case['checkpoint_sha256']
  inputs[case['checkpoint']]=case['checkpoint_sha256']
  model=YOLO(case['checkpoint']);assert model.names=={0:'knife'}
  for _ in range(3):predict(model,Image.new('RGB',(640,480)),640)
  cached_path=RUN/'predict/models'/name/'us-mock-reviewed/predictions.jsonl'
  inputs[str(cached_path)]=_sha256_file(cached_path)
  cached={(x['source_id'],x['frame_index']):x for x in read_rows(cached_path)}
  direct=[];maximum_tensor_error=0.;maximum_box_error=0.;maximum_score_error=0.;differences=[];max_roundtrip=0.;channel_checks=0
  for number,im in enumerate(truth['images'],1):
   image_path=Path(im['image']);assert _sha256_file(image_path)==im['image_sha256'];inputs[str(image_path)]=im['image_sha256']
   with Image.open(image_path) as source:rgb=source.convert('RGB')
   result=predict(model,rgb,640);boxes,scores,classes=raw_arrays(result)
   assert result.orig_shape==(im['height'],im['width']) and (classes==0).all()
   direct.append(frame(im,boxes,scores))
   old=cached[(im['source_id'],im['frame_index'])]['detections']
   if len(old)!=len(scores):differences.append({'image':number,'cached':len(old),'direct':len(scores)})
   elif len(old):
    db=float(np.max(np.abs(boxes-np.array([x['bbox_xyxy'] for x in old]))));ds=float(np.max(np.abs(scores-np.array([x['confidence'] for x in old]))))
    maximum_box_error=max(maximum_box_error,db);maximum_score_error=max(maximum_score_error,ds)
    if db>.001 or ds>1e-6:differences.append({'image':number,'max_box_delta':db,'max_score_delta':ds})
   # Independently rebuild the square 640 RGB tensor and reverse the GT box transform.
   bgr=np.asarray(rgb)[:,:,::-1].copy();g=min(640/im['width'],640/im['height'])
   nw,nh=round(im['width']*g),round(im['height']*g)
   px,py=(640-nw)/2,(640-nh)/2;left,top=round(px-.1),round(py-.1)
   manual=cv2.copyMakeBorder(cv2.resize(bgr,(nw,nh),interpolation=cv2.INTER_LINEAR),top,round(py+.1),left,round(px+.1),cv2.BORDER_CONSTANT,value=(114,114,114))[:,:,::-1].copy()
   actual=model.predictor.preprocess([bgr]).cpu().numpy()[0].transpose(1,2,0)
   err=float(np.max(np.abs(actual-manual.astype(np.float32)/255)));maximum_tensor_error=max(maximum_tensor_error,err)
   assert err<1e-6
   if im['knife_boxes_xyxy']:
    gt=np.array(im['knife_boxes_xyxy'],dtype=np.float64)
    projected=gt*g+np.array([left,top,left,top])
    restored=ops.scale_boxes((640,640),torch.tensor(projected,dtype=torch.float64),(im['height'],im['width'])).numpy()
    max_roundtrip=max(max_roundtrip,float(np.max(np.abs(restored-gt))))
    if ci==0:
     net=Image.fromarray(manual);net.save(OUT/'network-inputs'/f'{number:03d}.png')
   if number<=6:
    path_result=predict(model,str(image_path),640);pb,ps,pc=raw_arrays(path_result)
    array_result=predict(model,bgr,640);ab,asc,ac=raw_arrays(array_result)
    channel_checks+=1
    controls.append({'model':name,'image_no':number,'path_count':len(ps),'bgr_count':len(asc),'pil_count':len(scores),
      'jpeg_rgb_pixel_max_delta':int(np.max(np.abs(cv2.imread(str(image_path))[:,:,::-1].astype(np.int16)-np.asarray(rgb).astype(np.int16)))),
      'path_same_as_pil':len(ps)==len(scores) and bool(np.allclose(pb,boxes,atol=.001,rtol=0)) and bool(np.allclose(ps,scores,atol=1e-6,rtol=0)),
      'bgr_same_as_pil':len(asc)==len(scores) and bool(np.allclose(ab,boxes,atol=.001,rtol=0)) and bool(np.allclose(asc,scores,atol=1e-6,rtol=0))})
   if im['knife_boxes_xyxy']:
    overlaps=overlap_numpy(boxes,im['knife_boxes_xyxy'])
    official=box_iou(torch.tensor(boxes,dtype=torch.float64),torch.tensor(im['knife_boxes_xyxy'],dtype=torch.float64)).numpy()
    assert not overlaps.size or float(np.max(np.abs(overlaps-official)))<1e-6
    for gi,gt in enumerate(im['knife_boxes_xyxy']):
     high=[j for j,s in enumerate(scores) if overlaps[j,gi]>=.5]
     near=int(np.argmax(overlaps[:,gi])) if len(scores) else None
     gt_diagnostics.append({'model':name,'image_no':number,'source_id':im['source_id'],'gt_index':gi,
      'gt_xyxy':gt,'projected_640_width':(gt[2]-gt[0])*g,'projected_640_height':(gt[3]-gt[1])*g,
      'max_confidence_at_iou_ge05':float(max((scores[j] for j in high),default=0)),
      'highest_iou_any_candidate':float(overlaps[near,gi]) if near is not None else 0,
      'confidence_of_highest_iou':float(scores[near]) if near is not None else 0})
  write_rows(OUT/'predictions'/(name+'-direct640.jsonl'),direct)
  audit.append({'model':name,'images':83,'cached_direct_differences':differences,'max_box_delta_px':maximum_box_error,
   'max_score_delta':maximum_score_error,'max_network_tensor_delta':maximum_tensor_error,
   'gt_scale_roundtrip_error_px':max_roundtrip,'pil_path_bgr_images_checked':channel_checks,
   'actual_head_end2end':bool(model.predictor.model.end2end),'class_names':model.names})
  for size in [640,960,1280]:
   record(active=name,phase='fullframe_'+str(size))
   if size==640:predictions=direct
   else:
    predictions=[]
    for im in truth['images']:
     with Image.open(im['image']) as src:rgb=src.convert('RGB')
     boxes,scores,_=raw_arrays(predict(model,rgb,size));predictions.append(frame(im,boxes,scores))
    write_rows(OUT/'predictions'/(name+'-direct'+str(size)+'.jsonl'),predictions)
   for confidence in [.001,.05,.1,.25,.5]:
    result,_=evaluate_boxes(truth,predictions,{**POLICY,'confidence':confidence})
    independently=independent_counts(truth,predictions,confidence)
    assert independently=={k:result['counts'][k] for k in ['tp','fp','fn']}
    metrics.append({'model':name,'input':'fullframe','imgsz':size,'confidence':confidence,
      **independently,'recall':result['recall'],'precision':result['precision'],'f1':result['f1']})
  record(active=name,phase='gt_assisted_roi')
  roi_truth={**truth,'images':[]};roi_predictions=[]
  for number,im in enumerate(truth['images'],1):
   if not im['knife_boxes_xyxy']:continue
   gt=im['knife_boxes_xyxy'][0];assert len(im['knife_boxes_xyxy'])==1
   size=512
   assert max(gt[2]-gt[0],gt[3]-gt[1])<512
   x0=max(0,min(im['width']-size,round((gt[0]+gt[2])/2-size/2)))
   y0=max(0,min(im['height']-size,round((gt[1]+gt[3])/2-size/2)))
   with Image.open(im['image']) as src:crop=src.convert('RGB').crop((x0,y0,x0+size,y0+size))
   local=[gt[0]-x0,gt[1]-y0,gt[2]-x0,gt[3]-y0]
   roi_truth['images'].append({**im,'width':size,'height':size,'knife_boxes_xyxy':[local]})
   boxes,scores,_=raw_arrays(predict(model,crop,640));roi_predictions.append(frame(im,boxes,scores))
  write_rows(OUT/'predictions'/(name+'-gt-assisted-roi.jsonl'),roi_predictions)
  for confidence in [.1,.25]:
   result,_=evaluate_boxes(roi_truth,roi_predictions,{**POLICY,'confidence':confidence})
   metrics.append({'model':name,'input':'gt_assisted_roi_NOT_DEPLOYABLE','imgsz':640,'confidence':confidence,
    **{k:result['counts'][k] for k in ['tp','fp','fn']},'recall':result['recall'],'precision':result['precision'],'f1':result['f1']})
  del model;torch.cuda.empty_cache()
assert all(_sha256_file(Path(p))==digest for p,digest in inputs.items())
_write_json(OUT/'audit.json',{'status':'completed_diagnosis','models':audit,'channel_controls':controls,
 'oracle_control_counts':{k:oracle_metrics['counts'][k] for k in ['tp','fp','fn']},
 'native_zero_area_boxes_excluded_like_existing_canonical_adapter':discarded_zero_area,
 'input_sha256':inputs,'frozen_inputs_unchanged':True,'not_Orin_benchmark':True})
for filename,rows in [('metrics.csv',metrics),('gt-diagnostics.csv',gt_diagnostics)]:
 with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
record(status='passed',active=None,phase=None)
print(json.dumps({'status':'passed','models':len(cases),'metrics':metrics,'audit':audit}))
