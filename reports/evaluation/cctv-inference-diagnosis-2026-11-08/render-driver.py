"""Render exact cached boxes and GT; diagnostic crops never alter inference inputs."""
from pathlib import Path
import json,math,zipfile
from PIL import Image,ImageDraw,ImageFont

root=Path(r'C:\Class6\edge-threat-response')
data=root/'data/work/cctv-diagnostics-20261108-v2'
out=data/'visuals';out.mkdir(exist_ok=False)
for name in ['01_fullframe_comparison','02_gt_neighborhood_comparison','03_network_input_640','04_gt_assisted_roi_REFERENCE_ONLY']:(out/name).mkdir()
truth=json.loads((root/'runs/reviewed-cctv-20261106-v2/truth.json').read_text())
names={'raw-m1-n-640':'M1','raw-m2-n-640':'M2','raw-s1-n-640':'S1'}
rows=lambda p:[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
pred={n:{x['source_id']:x['detections'] for x in rows(data/'predictions'/(n+'-direct640.jsonl'))} for n in names}
roi={n:{x['source_id']:x['detections'] for x in rows(data/'predictions'/(n+'-gt-assisted-roi.jsonl'))} for n in names}
font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',20)
small=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',16)

def overlap(a,b):
 inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
 return inter/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)

def annotate(image,gts,ds,offset=(0,0),nearest=False):
 canvas=image.copy();draw=ImageDraw.Draw(canvas)
 shift=lambda b:(b[0]-offset[0],b[1]-offset[1],b[2]-offset[0],b[3]-offset[1])
 for box in gts:draw.rectangle(shift(box),outline='#00ff55',width=3)
 shown=[(d,'#ff3b30' if d['confidence']>=.25 else '#ffae42') for d in ds if d['confidence']>=.1]
 if nearest and gts and ds:
  best=max(ds,key=lambda d:overlap(d['bbox_xyxy'],gts[0]))
  if overlap(best['bbox_xyxy'],gts[0])>0 and best['confidence']<.1:shown.append((best,'#00ffff'))
 for d,color in shown:
  b=shift(d['bbox_xyxy'])
  if b[2]<0 or b[3]<0 or b[0]>canvas.width or b[1]>canvas.height:continue
  draw.rectangle(b,outline=color,width=2)
  draw.text((max(0,b[0]),max(0,b[1]-19)),f"{d['confidence']:.3f}",fill=color,stroke_fill='black',stroke_width=1,font=small)
 return canvas

def panel(image,width,height,title,subtitle):
 image.thumbnail((width,height))
 tile=Image.new('RGB',(width,height+65),'#202124')
 tile.paste(image,((width-image.width)//2,0))
 d=ImageDraw.Draw(tile);d.text((7,height+5),title,fill='white',font=font)
 d.text((7,height+33),subtitle,fill='white',font=small)
 return tile

selected=0
for index,im in enumerate(truth['images'],1):
 gts=im['knife_boxes_xyxy'];sid=im['source_id']
 if not gts and not any(d['confidence']>=.25 for n in names for d in pred[n][sid]):continue
 with Image.open(im['image']) as raw:image=raw.convert('RGB')
 full=Image.new('RGB',(1920,425),'#202124')
 for j,(name,label) in enumerate(names.items()):
  ds=pred[name][sid]
  tile=panel(annotate(image,gts,ds),640,360,f'{index:03d} | {label} full frame / 640 input',f"GT={len(gts)} | predictions >= .25: {sum(d['confidence']>=.25 for d in ds)}")
  full.paste(tile,(j*640,0))
 full.save(out/'01_fullframe_comparison'/f'{index:03d}.jpg',quality=95)
 if not gts:continue
 selected+=1;gt=gts[0];size=512
 x0=max(0,min(im['width']-size,round((gt[0]+gt[2])/2-size/2)))
 y0=max(0,min(im['height']-size,round((gt[1]+gt[3])/2-size/2)))
 crop=image.crop((x0,y0,x0+size,y0+size))
 near=Image.new('RGB',(1260,485),'#202124');assisted=near.copy()
 for j,(name,label) in enumerate(names.items()):
  ds=pred[name][sid]
  match=max((d['confidence'] for d in ds if overlap(d['bbox_xyxy'],gt)>=.5),default=0)
  tile=panel(annotate(crop,gts,ds,(x0,y0),nearest=True),420,420,f'{index:03d} | {label} full-frame predictions',f'Best score with IoU>=.5: {match:.4f}')
  near.paste(tile,(j*420,0))
  local=[gt[0]-x0,gt[1]-y0,gt[2]-x0,gt[3]-y0]
  rds=roi[name][sid]
  match=max((d['confidence'] for d in rds if overlap(d['bbox_xyxy'],local)>=.5),default=0)
  tile=panel(annotate(crop,[local],rds,nearest=True),420,420,f'{index:03d} | {label} GT-assisted crop',f'NOT DEPLOYMENT | score IoU>=.5: {match:.4f}')
  assisted.paste(tile,(j*420,0))
 near.save(out/'02_gt_neighborhood_comparison'/f'{index:03d}.png')
 assisted.save(out/'04_gt_assisted_roi_REFERENCE_ONLY'/f'{index:03d}.png')
 with Image.open(data/'network-inputs'/f'{index:03d}.png') as f:network=f.convert('RGB')
 gain=min(640/im['width'],640/im['height']);left=round((640-round(im['width']*gain))/2-.1);top=round((640-round(im['height']*gain))/2-.1)
 boxes=[[v*gain+(left if k%2==0 else top) for k,v in enumerate(gt)] for gt in gts]
 annotate(network,boxes,[]).save(out/'03_network_input_640'/f'{index:03d}.png')
assert selected==31
with zipfile.ZipFile(data/'visuals.zip','x',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(out).as_posix())
print(json.dumps({'positive_cases':31,'visual_files':len(list(out.rglob('*.png')))+len(list(out.rglob('*.jpg'))),'zip_bytes':(data/'visuals.zip').stat().st_size}))
