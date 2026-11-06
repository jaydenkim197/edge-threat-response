from pathlib import Path
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
import os
import sqlite3
import subprocess
import sys

ROOT = Path('C:/Class6/edge-threat-response')
SOURCE = Path('C:/Class6/etr-worktrees/e295586')
AUDIT = ROOT/'data/work/reviewed-next-training-20261106'
OUT = ROOT/'runs/reviewed-cctv-20261106-v2'
sys.path.insert(0,str(SOURCE/'src'))
from edge_threat_response.detector_comparison import POLICY
from edge_threat_response.training import _sha256_file, _write_json, gpu_training_lock

OUT.mkdir()
sys.stdout=(OUT/'worker.log').open('a',encoding='utf-8',buffering=1)
sys.stderr=sys.stdout
state={'status':'preparing','training_started':False,'final_detector_selected':False,
       'source_commit':'e29558681a76b2da82425b3e0ac096616c425eda',
       'worker_sha256':_sha256_file(Path(__file__))}


def record(**fields):
    state.update(fields);state['updated_at_utc']=datetime.now(timezone.utc).isoformat()
    _write_json(OUT/'state.json',state)


try:
    selected=[json.loads(x) for x in (AUDIT/'review-evidence-snapshot.jsonl').read_text(encoding='utf-8').splitlines()]
    selected=[x for x in selected if x['dataset']=='us-mock' and x['verdict']=='ok']
    config=json.loads((ROOT/'data/review/team-server/config.json').read_text())
    entry=next(x for x in config['datasets'] if x['id']=='us-mock')
    pack=Path(entry['review_dir'])
    evidence=[json.loads(x) for x in (pack/'image-evidence.jsonl').read_text().splitlines() if x.strip()]
    with closing(sqlite3.connect((pack/'human-review.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('BEGIN');current=dict((s,(v,p)) for s,v,p in db.execute('SELECT sample,version,payload FROM reviews'));db.rollback()
    baseline=ROOT/'data/processed/raw-real-20261105-v3/inventory.jsonl'
    train={x['image_sha256'] for x in map(json.loads,baseline.read_text().splitlines()) if x['split']=='train'}
    images,selection=[],[]
    previous=json.loads((ROOT/'data/work/multi-model-20261104/suite-v1/us-mock-truth.json').read_text())
    opened={x['image_sha256'] for x in previous['images']}
    for index,row in enumerate(selected):
        version,payload=current[row['sample']]
        import hashlib
        assert version==row['version'] and hashlib.sha256(payload.encode()).hexdigest()==row['review_payload_sha256']
        ev=evidence[row['sample']];image=pack/ev['image_file']
        assert _sha256_file(image)==row['image_sha256'] and row['image_sha256'] not in train
        group=ev['source_group']
        for b in row['boxes']:assert 0<=b[0]<b[2]<=row['width'] and 0<=b[1]<b[3]<=row['height']
        if not row['knife_count']:assert row['negative_knife_absence']=='yes'
        images.append({'source_id':'us-reviewed-'+row['image_sha256'][:20],'frame_index':0,
                       'image_sha256':row['image_sha256'],'image':str(image),'source_path':row['image_path'],
                       'source_group':group,'width':row['width'],'height':row['height'],
                       'knife_boxes_xyxy':row['boxes'],'knife_absence_verified':not bool(row['knife_count'])})
        selection.append({'sample':row['sample'],'version':row['version'],'image_sha256':row['image_sha256'],
                          'review_payload_sha256':row['review_payload_sha256'],
                          'previously_opened_development_image':row['image_sha256'] in opened})
    assert len(images)==83 and sum(len(x['knife_boxes_xyxy']) for x in images)==31
    truth={'schema_version':1,'status':'development_authorized','partition':'tuning',
           'source_group_basis':'source sequence; includes previously opened development images',
           'images':images}
    _write_json(OUT/'truth.json',truth);_write_json(OUT/'selection.json',selection)
    suite={'schema_version':1,'status':'development_authorized','policy':POLICY,
           'inputs':{str(OUT/'selection.json'):_sha256_file(OUT/'selection.json')},
           'datasets':{'us-mock-reviewed':{'truth':str(OUT/'truth.json'),'truth_sha256':_sha256_file(OUT/'truth.json'),
                    'images':len(images),'knife_objects':31,'groups':len({x['source_group'] for x in images}),
                    'role':'external real CCTV development evaluation only','previous_opened_images':len(opened)}}}
    _write_json(OUT/'suite.json',suite)
    protocol=json.loads((ROOT/'runs/raw-followup-20261106-recovery-v1/predict/models.json').read_text())
    cases=[dict(x) for x in protocol['cases'] if x['id'] in {'custom-n-640','raw-m1-n-640','raw-m1-s-640','rf-large-704'}]
    extra=dict(next(x for x in cases if x['id']=='raw-m1-n-640'));extra.update(id='raw-m1-n-960',imgsz=960);cases.append(extra)
    protocol.update(cases=cases,suite_sha256=_sha256_file(OUT/'suite.json'),
                    experiment='reviewed external CCTV expansion; no model retraining or final-test claim')
    _write_json(OUT/'models.json',protocol)
    env={**os.environ,'PYTHONPATH':str(SOURCE/'src'),'YOLO_AUTOINSTALL':'false','PYTHONUTF8':'1'}
    with gpu_training_lock(ROOT/'runs/training/gpu0-training.lock',owner='reviewed-cctv-20261106-v1'):
        for case in cases:
            record(status='evaluating',active_model=case['id'])
            with (OUT/(case['id']+'.log')).open('x',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-X','utf8',str(SOURCE/'tools/run_detector_comparison.py'),
                    '--suite',str(OUT/'suite.json'),'--models',str(OUT/'models.json'),'--case',case['id'],
                    '--output',str(OUT/'models'/case['id']),'--authorize-development-comparison'],
                    cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    with (OUT/'aggregate.log').open('x',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-X','utf8',str(SOURCE/'tools/summarize_detector_comparison.py'),
            '--suite',str(OUT/'suite.json'),'--models',str(OUT/'models.json'),'--runs',str(OUT/'models'),
            '--output',str(OUT/'aggregate')],cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    record(status='passed',active_model=None,images=83,knife_gt=31,negative_images=52,
           models=5,previous_opened_images=21,review_database_modified=False)
except BaseException as error:
    record(status='failed',error=type(error).__name__+': '+str(error));raise
