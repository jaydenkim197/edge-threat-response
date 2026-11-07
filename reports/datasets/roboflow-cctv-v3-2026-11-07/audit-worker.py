"""One-off bounded source audit; never mutate production reviews or training inputs."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
import zipfile

ROOT = Path('C:/Class6/edge-threat-response')
SOURCE = ROOT/'data/source-audit/roboflow-cctv-v3-20261106'
OUT = ROOT/'data/work/roboflow-cctv-v3-20261107'
PACK = ROOT/'data/review/prepared-candidates-20261107/roboflow-cctv-v3'
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from PIL import Image, ImageChops, ImageDraw, ImageStat
from edge_threat_response.dataset.image_screening import image_signature, similarity_pairs
from edge_threat_response.dataset.development_subset import proxy_components
from edge_threat_response.dataset.review_web import ReviewStore
import prepare_team_review

EXPECTED_ARCHIVE = '3d46ab82c263b6f8429301b6d7b6863c53db49fa11d9d05f0092484ed604149d'
archive = SOURCE/'candidate-source.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == EXPECTED_ARCHIVE
source = SOURCE/'source'
assert not source.exists() and not OUT.exists() and not PACK.exists(), 'Use fresh outputs; preserve prior evidence'
OUT.mkdir(parents=True)
source.mkdir()
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == 48
    for name in z.namelist():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
    z.extractall(source)

def rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

metadata = json.loads((source/'source-records.json').read_text(encoding='utf-8'))
assert len(metadata['rows']) == len({r['id'] for r in metadata['rows']}) == 50
records, problems = [], []
for row in metadata['rows']:
    if not row['image_file']:
        problems.append({'sample_no':row['sample_no'], 'image_id':row['id'], 'reason':'original_not_bundled'})
        continue
    image = source/row['image_file']
    signature = image_signature(image, expected_sha256=row['image_sha256'])
    assert signature['width']==row['width'] and signature['height']==row['height']
    assert signature['exif_orientation'] == 1
    knives, all_boxes = [], []
    for label,cx,cy,w,h in row['boxes_label_cx_cy_w_h']:
        assert all(math.isfinite(x) for x in (cx,cy,w,h)) and w>0 and h>0
        box = [cx-w/2, cy-h/2, cx+w/2, cy+h/2]
        # Retain provider values; source decimal rounding can put a person edge .005px out.
        assert box[0]>=-.05 and box[1]>=-.05 and box[2]<=row['width']+.05 and box[3]<=row['height']+.05
        all_boxes.append({'label':label,'bbox_xyxy':box})
        if label in {'knife','Knife'}:
            assert 0<=box[0]<box[2]<=row['width'] and 0<=box[1]<box[3]<=row['height']
            knives.append(box)
    records.append({**row, **signature, 'record_id':'roboflow-cctv-v3/'+row['id'],
                    'dataset_id':'roboflow-cctv-v3', 'original_split':row['split'],
                    'image_file':str(image), 'all_boxes':all_boxes, 'knife_boxes':knives,
                    'knife_count':len(knives),
                    'knife_normalized_areas':[(b[2]-b[0])*(b[3]-b[1])/(row['width']*row['height']) for b in knives],
                    'training_approved':False})
assert len(records)==47

# Cached full RAW source inventory is read-only. Add every US review image, covering
# the entire expanded 83-image opened development set without reading human payloads.
signature_path = ROOT/'data/processed/raw-real-20261105-v2/signatures.jsonl'
pair_path = ROOT/'data/processed/raw-real-20261105-v2/similarity-pairs.jsonl'
inventory_path = ROOT/'data/processed/raw-real-20261105-v3/inventory.jsonl'
references = rows(signature_path)
group = proxy_components(references, rows(pair_path))
inventory = rows(inventory_path)
protected_groups = {group[r['record_id']] for r in references if r['dataset_id']=='protected'}
protected_groups |= {r['source_group'] for r in inventory if r['split'] in {'val','test'}}
config_path = ROOT/'data/review/team-server/config.json'
input_hashes = {str(p):sha(p) for p in (signature_path,pair_path,inventory_path,config_path)}
config = json.loads(config_path.read_text())
us_entry = next(r for r in config['datasets'] if r['id']=='us-mock')
us_paths = [Path(us_entry['review_dir']), *[Path(b['review_dir']) for b in us_entry.get('review_batches',[])]]
us_count=0
for pack in us_paths:
    path=pack/'image-evidence.jsonl';input_hashes[str(path)]=sha(path)
    for item in rows(path):
        sig=image_signature(pack/item['image_file'],expected_sha256=item['image_sha256'])
        references.append({**sig,'record_id':'us-review/'+str(us_count)+'/'+item['image_path'],
                           'dataset_id':'us-mock-review','original_split':'protected_development',
                           'image_file':str(pack/item['image_file'])})
        us_count+=1
assert us_count>=100

links=[]; best=[]
for record in records:
    found=[]
    value=int(record['dhash64'],16)
    for other in references:
        exact=record['image_sha256']==other['image_sha256']
        hamming=(value^int(other['dhash64'],16)).bit_count()
        if not exact and (hamming>4 or record['low_information'] or other['low_information']):
            continue
        standard=bool(similarity_pairs([record,other],4))
        other_group=group.get(other['record_id'])
        match={'sample_no':record['sample_no'],'image_id':record['id'],
               'reference_id':other['record_id'],'reference_dataset':other['dataset_id'],
               'exact_bytes':exact,'hamming_distance':hamming,'standard_aspect_gate':standard,
               'screen_type':'exact' if exact else ('dhash4_aspect' if standard else 'dhash4_stretch_candidate'),
               'protected_group_link':other_group in protected_groups or other['dataset_id'] in {'protected','us-mock-review'},
               'reference_image':other.get('image_file')}
        # A grayscale, aspect-normalized pixel difference supports manual inspection;
        # it is never an automatic dataset acceptance rule.
        if match['reference_image'] and Path(match['reference_image']).is_file():
            with Image.open(record['image_file']) as a, Image.open(match['reference_image']) as b:
                a=a.convert('L').resize((64,64),Image.Resampling.LANCZOS)
                b=b.convert('L').resize((64,64),Image.Resampling.LANCZOS)
                match['gray_mae_64']=ImageStat.Stat(ImageChops.difference(a,b)).mean[0]
        found.append(match)
    found.sort(key=lambda x:(not x['exact_bytes'],x.get('gray_mae_64',999),x['hamming_distance'],x['reference_dataset']))
    links.extend(found)
    if found: best.append(found[0])
    record['near_reference_count']=len(found)
    record['near_sources']=sorted({x['reference_dataset'] for x in found})
    record['protected_link']=any(x['protected_group_link'] for x in found)

internal = similarity_pairs(records,4)
write_json(OUT/'integrity-summary.json',{'downloaded':len(records),'metadata':50,'problems':problems,
    'image_bytes':sum(r['image_bytes'] for r in records),'exif_orientation_all_1':True,
    'image_dimensions_match_annotations':True,'knife_coordinate_bounds_valid':True,
    'within_sample_standard_similarity_pairs':internal,
    'notes':['Provider original.jpg means project-uploaded image, not a verified original camera frame.',
             'Current browser annotations are not verified to equal frozen export-v1 annotations.',
             'No knife label does not establish knife absence.']})
write_json(OUT/'reference-inputs.json',{'source_sha256':input_hashes,
    'reference_counts':dict(Counter(r['dataset_id'] for r in references)),
    'us_mock_scope':'All 100 immutable review images, including all 83 opened development images; not all 5,149 real frames'})
write_json(OUT/'duplicate-links.json',links)
write_json(OUT/'best-matches.json',best)
write_json(OUT/'records.json',records)

def tile(path, title, boxes=(), size=(480,320)):
    canvas=Image.new('RGB',size,'#1e2024')
    with Image.open(path) as opened:
        image=opened.convert('RGB');w,h=image.size
    image.thumbnail((size[0],size[1]-50))
    x,y=(size[0]-image.width)//2,0
    canvas.paste(image,(x,y));draw=ImageDraw.Draw(canvas)
    for label,b in boxes:
        b=[x+b[0]*image.width/w,y+b[1]*image.height/h,x+b[2]*image.width/w,y+b[3]*image.height/h]
        draw.rectangle(b,outline='#ff5d5d' if label in {'knife','Knife'} else '#47dd9a',width=2)
    draw.text((6,size[1]-45),title,fill='white')
    return canvas

(OUT/'contact-sheets').mkdir()
for start in range(0,len(records),12):
    sheet=Image.new('RGB',(1440,1280),'white')
    for j,r in enumerate(records[start:start+12]):
        image=tile(r['image_file'],f"{r['sample_no']:02d} {r['name']} | {r['width']}x{r['height']}\nknife={r['knife_count']} near={r['near_reference_count']}",[(b['label'],b['bbox_xyxy']) for b in r['all_boxes']])
        sheet.paste(image,((j%3)*480,(j//3)*320))
    sheet.save(OUT/'contact-sheets'/f'page-{start//12+1:02d}.jpg',quality=92)
(OUT/'pair-sheets').mkdir()
by_id={r['id']:r for r in records}
available=[b for b in best if b.get('reference_image') and Path(b['reference_image']).is_file()]
for start in range(0,len(available),6):
    sheet=Image.new('RGB',(960,1920),'white')
    for j,b in enumerate(available[start:start+6]):
        r=by_id[b['image_id']]
        sheet.paste(tile(r['image_file'],f"CCTV-V3 {r['sample_no']:02d} {r['name']}",[(x['label'],x['bbox_xyxy']) for x in r['all_boxes']]),(0,j*320))
        sheet.paste(tile(b['reference_image'],f"{b['reference_dataset']} exact={b['exact_bytes']} h={b['hamming_distance']}\nMAE={b.get('gray_mae_64',-1):.2f} protected={b['protected_group_link']}"),(480,j*320))
    sheet.save(OUT/'pair-sheets'/f'page-{start//6+1:02d}.jpg',quality=92)

# Prepare a separate immutable candidate pack, never register it with the live server.
# Only the 40 downloaded images with a knife label are useful for its two questions.
samples=[]
for r in records:
    if not r['knife_count']:continue
    samples.append({'image_path':r['name'],'bytes':Path(r['image_file']).read_bytes(),
                    'boxes':r['knife_boxes'],'original_split':r['split'],
                    'source_revision':'public-browser-snapshot-2026-11-06',
                    'source_image_id':r['id'],'audit_sample_no':r['sample_no'],
                    'source_url':metadata['source_url']+'/images/'+r['id'],
                    'near_sources':r['near_sources'],'protected_link':r['protected_link']})
prepare_team_review.PACKS=PACK.parent
pack_summary=prepare_team_review.write_pack(PACK.name,samples,{
    'role':'bounded source suitability audit; not approved training data',
    'license':'CC BY 4.0 displayed; original source provenance unverified',
    'source_url':metadata['source_url'],'selection':metadata['selection'],
    'live_site_registered':False,'do_not_admit_without_duplicate_group_review':True})
qa=OUT/'qa';qa.mkdir()
store=ReviewStore(PACK,database=qa/'compatibility.sqlite3')
assert len(store.items())==len(samples)==40
with store.connect() as db:
    assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM history').fetchone()[0]==0
write_json(OUT/'pack-compatibility.json',{'pack':str(PACK),'images':len(samples),
    'pack_hash':store.pack_hash,'review_store_loaded':True,'qa_reviews':0,'qa_history':0,
    'human_reviewer_fields_blank':True,'production_store_initialized':False,'live_site_registered':False})

for path,digest in input_hashes.items():assert sha(Path(path))==digest,'Read-only reference changed'
summary={'finished_at_utc':datetime.now(timezone.utc).isoformat(),
    'git_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
    'worker_sha256':sha(Path(__file__)),'archive_sha256':EXPECTED_ARCHIVE,
    'metadata_images':50,'images_downloaded_decoded':47,'missing_original_images':3,
    'knife_images':sum(r['knife_count']>0 for r in records),'knife_objects':sum(r['knife_count'] for r in records),
    'class_objects':dict(Counter(b['label'] for r in records for b in r['all_boxes'])),
    'knife_and_person_labeled_images':sum(r['knife_count']>0 and any(b['label']=='person' for b in r['all_boxes']) for r in records),
    'small_knife_images_area_le_02':sum(any(a<=.02 for a in r['knife_normalized_areas']) for r in records),
    'knife_area_range':[min(a for r in records for a in r['knife_normalized_areas']),max(a for r in records for a in r['knife_normalized_areas'])],
    'byte_exact_reference_images':len({b['image_id'] for b in links if b['exact_bytes']}),
    'standard_near_reference_images':len({b['image_id'] for b in links if b['standard_aspect_gate']}),
    'any_dhash4_reference_images':len({b['image_id'] for b in links}),
    'protected_direct_link_images':sum(r['protected_link'] for r in records),
    'reference_counts':dict(Counter(r['dataset_id'] for r in references)),
    'source_and_production_config_hashes_unchanged':True,
    'candidate_pack':str(PACK),'candidate_pack_images':pack_summary['images'],
    'live_site_registered':False,'training_inputs_modified':False,'training_approved':False,
    'human_verdicts_written':0,'visual_pre_review':'pending; contact/pair sheets prepared'}
write_json(OUT/'summary.json',summary)
with zipfile.ZipFile(OUT/'audit-artifacts.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
    for f in sorted(OUT.rglob('*')):
        if f.is_file() and f.suffix!='.zip' and not f.is_relative_to(qa):z.write(f,f.relative_to(OUT).as_posix())
print(json.dumps(summary,ensure_ascii=True),flush=True)
