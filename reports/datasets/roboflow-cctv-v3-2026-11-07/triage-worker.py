"""Supplement source audit with seven bounded target/gap candidates; no admission."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import heapq
import json
import sys
import zipfile

ROOT=Path('C:/Class6/edge-threat-response')
OUT=ROOT/'data/work/roboflow-cctv-v3-20261107'
TRIAGE=OUT/'triage'
PACK=ROOT/'data/review/prepared-candidates-20261107/roboflow-cctv-v3-target-shortlist'
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from PIL import Image,ImageChops,ImageDraw,ImageStat
from edge_threat_response.dataset.review_web import ReviewStore
import prepare_team_review

assert not TRIAGE.exists() and not PACK.exists()
TRIAGE.mkdir()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
records=load(OUT/'records.json')
references=[json.loads(x) for x in (ROOT/'data/processed/raw-real-20261105-v2/signatures.jsonl').read_text(encoding='utf-8-sig').splitlines() if x.strip()]
selected=[r for r in records if r['sample_no'] in {3,12,15,16,21,25,47}]
assert len(selected)==7 and all(r['knife_count']==1 and not r['protected_link'] and not r['near_reference_count'] for r in selected)
results=[]
def small(path):
    with Image.open(path) as image:return image.convert('L').resize((64,64),Image.Resampling.LANCZOS)
for r in selected:
    value=int(r['dhash64'],16)
    closest=heapq.nsmallest(10,references,key=lambda x:(value^int(x['dhash64'],16)).bit_count())
    candidate=small(r['image_file'])
    matches=[]
    for other in closest:
        distance=(value^int(other['dhash64'],16)).bit_count()
        path=Path(other['image_file'])
        mae=ImageStat.Stat(ImageChops.difference(candidate,small(path))).mean[0] if path.is_file() else None
        matches.append({'reference_id':other['record_id'],'dataset_id':other['dataset_id'],
                        'hamming_distance':distance,'gray_mae_64':mae,'image_file':str(path)})
    results.append({'sample_no':r['sample_no'],'id':r['id'],'name':r['name'],
                    'minimum_reference_hamming':matches[0]['hamming_distance'],
                    'closest_screening_references':matches,
                    'novelty_verified':False,'group_independence_verified':False})

def tile(path,title,box=None):
    out=Image.new('RGB',(480,320),'#202124')
    with Image.open(path) as image:
        image=image.convert('RGB');w,h=image.size;image.thumbnail((480,270))
    x=(480-image.width)//2;out.paste(image,(x,0));draw=ImageDraw.Draw(out)
    if box:draw.rectangle((x+box[0]*image.width/w,box[1]*image.height/h,x+box[2]*image.width/w,box[3]*image.height/h),outline='#ff5555',width=2)
    draw.text((5,276),title,fill='white');return out

sheet=Image.new('RGB',(1440,960),'white')
for i,r in enumerate(selected):
    scene='parking_high_angle_proxy' if r['sample_no']==15 else 'red_shirt_room_proxy'
    sheet.paste(tile(r['image_file'],f"{r['sample_no']:02d} {r['name']}\n{scene}",r['knife_boxes'][0]),((i%3)*480,(i//3)*320))
sheet.save(TRIAGE/'shortlist.jpg',quality=95)
nearest=Image.new('RGB',(960,2240),'white')
by_no={r['sample_no']:r for r in selected}
for i,result in enumerate(results):
    r=by_no[result['sample_no']];b=min(result['closest_screening_references'],key=lambda x:x['gray_mae_64'] if x['gray_mae_64'] is not None else 999)
    nearest.paste(tile(r['image_file'],f"CCTV-V3 {r['sample_no']:02d}",r['knife_boxes'][0]),(0,i*320))
    nearest.paste(tile(b['image_file'],f"Nearest of ten: {b['dataset_id']}\nh={b['hamming_distance']} MAE={b['gray_mae_64']:.2f}"),(480,i*320))
nearest.save(TRIAGE/'nearest-reference-sheet.jpg',quality=92)
write(TRIAGE/'nearest-references.json',results)

samples=[]
for r in selected:
    samples.append({'image_path':r['name'],'bytes':Path(r['image_file']).read_bytes(),
                    'boxes':r['knife_boxes'],'original_split':r['split'],
                    'source_revision':'public-browser-snapshot-2026-11-06','source_image_id':r['id'],
                    'audit_sample_no':r['sample_no'],
                    'source_url':'https://universe.roboflow.com/weapon-detection-cctv/weapon-detection-cctv-v3-dataset/images/'+r['id'],
                    'scene_proxy':'parking_high_angle_proxy' if r['sample_no']==15 else 'red_shirt_room_proxy',
                    'scene_proxy_confirmed_session':False,'training_approved':False})
prepare_team_review.PACKS=PACK.parent
prepare_team_review.write_pack(PACK.name,samples,{'role':'seven bounded gap candidates; human review pending',
    'license':'CC BY 4.0 displayed; original provenance unverified','full_source_audit':str(OUT),
    'selection':'6 same-room small-knife frames + 1 high-angle parking frame; not independent scenes or confirmed Holding GT',
    'candidate_scene_families':2,'live_site_registered':False,'training_approved':False})
qa=TRIAGE/'qa';qa.mkdir()
store=ReviewStore(PACK,database=qa/'compatibility.sqlite3')
assert len(store.items())==7
with store.connect() as db:
    assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM history').fetchone()[0]==0
summary={'finished_at_utc':datetime.now(timezone.utc).isoformat(),'worker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'shortlist_images':7,'candidate_scene_families':2,'high_angle_target_like_images':1,'other_fixed_room_small_knife_images':6,
    'pack_path':str(PACK),'pack_hash':store.pack_hash,'review_store_load_passed':True,
    'human_verdicts_written':0,'live_site_registered':False,'training_approved':False,
    'minimum_reference_hamming':{str(r['sample_no']):r['minimum_reference_hamming'] for r in results},
    'limitations':['Screening is not proof of no overlap, full sequence independence or real CCTV provenance.',
                   'Class presence or co-occurrence is not Holding ground truth.']}
write(TRIAGE/'summary.json',summary)
with zipfile.ZipFile(TRIAGE/'triage-artifacts.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
    for f in sorted(TRIAGE.rglob('*')):
        if f.is_file() and f.suffix!='.zip' and not f.is_relative_to(qa):z.write(f,f.relative_to(TRIAGE).as_posix())
print(json.dumps(summary),flush=True)
