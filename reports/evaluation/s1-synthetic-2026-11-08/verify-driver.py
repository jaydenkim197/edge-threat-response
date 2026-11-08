"""Verify the completed S1 experiment using existing metrics, without inference."""
from pathlib import Path
import csv,datetime,json,sys

ROOT=Path(r'C:\Class6\edge-threat-response')
SOURCE=Path(r'C:\Class6\etr-worktrees\s1-20261108-run')
RUN=ROOT/'runs/s1-comparison-20261108-v1'
sys.path.insert(0,str(SOURCE/'src'))
from edge_threat_response.training import _sha256_file,_write_json
from edge_threat_response.detector_comparison import POLICY,coco_metrics
from edge_threat_response.detection_evaluation import evaluate_boxes

load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
rows=lambda p:[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
state=load(RUN/'state.json')
queue_path=ROOT/'data/processed/s1-synthetic-20261108-v2-profiles/queue.json'
queue=load(queue_path)
training=load(ROOT/'runs/training/s1-synthetic-20261108-v2-queue-state.json')
inv_path=ROOT/'runs/training/s1-synthetic-20261108-v2-raw-s1-n-invocation.json'
inv=load(inv_path)
assert state['status']==training['status']==inv['status']=='passed'
assert state['queue_sha256']==training['queue_sha256']==_sha256_file(queue_path)
assert inv['observed_optimizer_updates']==queue['planned_updates_each']==37700
save=Path(inv['save_dir'])
history=list(csv.DictReader((save/'results.csv').open(encoding='utf-8-sig')))
assert len(history)==50 and [int(x['epoch']) for x in history]==list(range(1,51))
artifact_checks={}
for name in ['best.pt','last.pt','results.csv']:
 artifact,= [a for a in inv['artifacts'] if Path(a['path']).name==name]
 assert _sha256_file(Path(artifact['path']))==artifact['sha256']
 artifact_checks[name]=artifact['sha256']
suite=load(RUN/'suite.json')
for path,digest in suite['inputs'].items(): assert _sha256_file(Path(path))==digest
unique=set()
for item in suite['datasets'].values():
 assert _sha256_file(Path(item['truth']))==item['truth_sha256']
 for image in load(Path(item['truth']))['images']:
  assert _sha256_file(Path(image['image']))==image['image_sha256']
  unique.add(image['image_sha256'])
assert len(unique)==325
checked=0
new_ap_checked=0
for track in ['predict','ap']:
 dest=RUN/track
 protocol=load(dest/'models.json')
 assert protocol['suite_sha256']==_sha256_file(RUN/'suite.json')
 fixed=list(csv.DictReader((dest/'aggregate/comparison.csv').open(encoding='utf-8-sig')))
 curves=list(csv.DictReader((dest/'thresholds.csv').open(encoding='utf-8-sig')))
 assert len(fixed)==28 and len(curves)==308
 assert load(dest/'reference-reproduction.json')['partitions']==21
 for case in protocol['cases']:
  assert _sha256_file(Path(case['checkpoint']))==case['checkpoint_sha256']
  case_root=dest/'models'/case['id']
  summary=load(case_root/'summary.json')
  assert summary['models_sha256']==_sha256_file(dest/'models.json')
  assert summary['suite_sha256']==_sha256_file(RUN/'suite.json')
  for name,dataset in suite['datasets'].items():
   truth=load(Path(dataset['truth']))
   partition=summary['results'][name]
   pred_path=case_root/name/'predictions.jsonl'
   assert _sha256_file(pred_path)==partition['predictions_sha256']
   assert partition['truth_sha256']==dataset['truth_sha256']
   predictions=rows(pred_path)
   metrics,_=evaluate_boxes(truth,predictions,POLICY)
   assert metrics==partition['fixed']
   curve,=[c for c in curves if c['model']==case['id'] and c['dataset']==name and float(c['confidence'])==.25]
   for key in ['tp','fp','fn']: assert int(curve[key])==metrics['counts'][key]
   if case['id']=='raw-s1-n-640':
    ap=coco_metrics(truth,predictions)
    for key in ['ap50','ap50_95']:
     assert abs(ap[key]-partition['coco'][key])<1e-12
    new_ap_checked+=1
   checked+=1
out=RUN/'analysis'
out.mkdir(exist_ok=False)
result={'status':'passed','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'training_epochs':50,'actual_optimizer_updates':37700,'results_csv_seconds':float(history[-1]['time']),
 'artifact_sha256':artifact_checks,'prediction_and_fixed_partitions_checked':checked,
 's1_ap_partitions_recomputed':new_ap_checked,'reference_partitions_reproduced':42,
 'fixed_rows_each_track':28,'threshold_rows_each_track':308,'unique_images':325,
 'frozen_input_and_image_hashes_preserved':True,'final_detector_selected':False,'orin_verified':False}
_write_json(out/'verification.json',result)
print(json.dumps(result))
