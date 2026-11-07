"""Verify immutable input/pack contracts and run existing focused tests in isolation."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import sqlite3
import subprocess
import sys

ROOT=Path('C:/Class6/edge-threat-response')
OUT=ROOT/'data/work/roboflow-cctv-v3-20261107'
QA=OUT/'qa'
results=[]
for pattern in ['test_image_screening.py','test_review_web.py']:
    run=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern],
                       cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (QA/(pattern+'.log')).write_bytes(run.stdout)
    text=run.stdout.decode('utf-8',errors='replace')
    results.append({'pattern':pattern,'returncode':run.returncode,'tail':text.splitlines()[-4:]})
    print(pattern,run.returncode,text[-500:])
    assert run.returncode==0

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
references=json.loads((OUT/'reference-inputs.json').read_text(encoding='utf-8'))
for path,digest in references['source_sha256'].items():assert sha(Path(path))==digest
packs=[]
for name,expected in [('roboflow-cctv-v3',40),('roboflow-cctv-v3-target-shortlist',7)]:
    pack=ROOT/'data/review/prepared-candidates-20261107'/name
    csv_bytes=(pack/'review.csv').read_bytes();evidence_bytes=(pack/'image-evidence.jsonl').read_bytes()
    rows=list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'))))
    evidence=[json.loads(x) for x in evidence_bytes.decode().splitlines() if x]
    assert len(rows)==len(evidence)==expected and all(not x['reviewer'] for x in rows)
    assert all(not x['training_approved'] for x in evidence)
    for x in evidence:assert sha(pack/x['image_file'])==x['image_sha256']
    assert not (pack/'human-review.sqlite3').exists(), 'Candidate pack must not contain runtime human verdicts'
    packs.append({'name':name,'images':expected,'pack_hash':hashlib.sha256(csv_bytes+evidence_bytes).hexdigest(),
                  'all_image_sha256_match':True,'all_reviewer_fields_blank':True,'human_db_created_in_pack':False})

q=(OUT/'qa/compatibility.sqlite3').resolve().as_uri()+'?mode=ro'
with sqlite3.connect(q,uri=True) as db:
    assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM history').fetchone()[0]==0
q=(OUT/'triage/qa/compatibility.sqlite3').resolve().as_uri()+'?mode=ro'
with sqlite3.connect(q,uri=True) as db:
    assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM history').fetchone()[0]==0
result={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'tests':results,'packs':packs,
        'reference_inputs_and_production_config_unchanged':True,
        'production_review_store_instantiated':False,'production_verdicts_written':0,
        'training_launched':False,'live_site_registered':False,
        'limitations':['No live-site registration or mobile UI QA for this new candidate pack.',
                       'No performance evaluation or hardware test in this task.']}
(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=True),flush=True)
