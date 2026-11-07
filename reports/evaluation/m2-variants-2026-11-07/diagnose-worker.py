"""CCTV localization sensitivity only; never replace the primary IoU=.5 policy."""
import csv,json,sys
from pathlib import Path
ROOT=Path(r'C:\Class6\edge-threat-response\runs\m2-variants-comparison-20261107-v1')
sys.path.insert(0,r'C:\Class6\etr-worktrees\m2-comparison-20261107\src')
from edge_threat_response.detector_comparison import POLICY
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.training import _sha256_file
suite=json.loads((ROOT/'suite.json').read_text());data=suite['datasets']['us-mock-reviewed']
truth_path=Path(data['truth']);assert _sha256_file(truth_path)==data['truth_sha256']
truth=json.loads(truth_path.read_text());result=[]
protocol=json.loads((ROOT/'predict/models.json').read_text())
for case in protocol['cases']:
 p=ROOT/'predict/models'/case['id']/'us-mock-reviewed/predictions.jsonl'
 summary=json.loads((p.parent/'summary.json').read_text());assert _sha256_file(p)==summary['predictions_sha256']
 rows=[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
 for confidence in (.001,.1,.25):
  for overlap in (.25,.3,.5):
   metrics,_=evaluate_boxes(truth,rows,{**POLICY,'confidence':confidence,'iou':overlap})
   result.append({'model':case['id'],'confidence':confidence,'match_iou':overlap,**{k:metrics['counts'][k] for k in ('tp','fp','fn')}})
out=ROOT/'analysis/iou-diagnostic.csv'
with out.open('x',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
for r in result:
 if r['confidence']==.25 and r['match_iou'] in (.25,.5):print(json.dumps(r))
