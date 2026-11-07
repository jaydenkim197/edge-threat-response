"""PC13 CPU-only cached M1-n/s NMS ensemble, using frozen opened suites."""
import argparse
import csv
import json
import sys
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.source/'src'))
from edge_threat_response.detector_comparison import POLICY, nms_ensemble, coco_metrics, paired_group_recall_interval
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.training import _sha256_file, _write_json, _git_commit
from edge_threat_response.replay import write_jsonl
ROOT=Path(r'C:\Class6\edge-threat-response')
if a.output.exists():raise ValueError('Fresh output required')
a.output.mkdir(parents=True)
state={'status':'running','source_commit':_git_commit(),'worker_sha256':_sha256_file(Path(__file__)),
       'training_started':False,'final_detector_selected':False,'inference_latency_measured':False}
_write_json(a.output/'state.json',state)
inputs={}
results=[]
try:
    for suite_path,models_path,runs in (
      (ROOT/'data/work/multi-model-20261104/suite-v1/suite.json',ROOT/'runs/raw-followup-20261106-recovery-v1/predict/models.json',ROOT/'runs/raw-followup-20261106-recovery-v1/predict/models'),
      (ROOT/'runs/reviewed-cctv-20261106-v2/suite.json',ROOT/'runs/reviewed-cctv-20261106-v2/models.json',ROOT/'runs/reviewed-cctv-20261106-v2/models')):
        suite=json.loads(suite_path.read_text()); protocol=json.loads(models_path.read_text())
        for f in (suite_path,models_path):inputs[str(f)]=_sha256_file(f)
        assert protocol['suite_sha256']==_sha256_file(suite_path)
        cases={c['id']:c for c in protocol['cases']}
        members=['raw-m1-n-640','raw-m1-s-640']
        summaries={}
        for name in members:
            case=cases[name]
            assert _sha256_file(Path(case['checkpoint']))==case['checkpoint_sha256']
            summary_path=runs/name/'summary.json'
            s=json.loads(summary_path.read_text()); inputs[str(summary_path)]=_sha256_file(summary_path)
            assert s['status']=='completed_development_comparison' and s['case']==case
            assert s['suite_sha256']==_sha256_file(suite_path) and s['models_sha256']==_sha256_file(models_path)
            summaries[name]=s
        for name,dataset in suite['datasets'].items():
            truth_path=Path(dataset['truth']);assert _sha256_file(truth_path)==dataset['truth_sha256']
            inputs[str(truth_path)]=_sha256_file(truth_path)
            truth=json.loads(truth_path.read_text());predictions=[]
            for member in members:
                path=runs/member/name/'predictions.jsonl'; inputs[str(path)]=_sha256_file(path)
                assert summaries[member]['results'][name]['predictions_sha256']==inputs[str(path)]
                predictions.append([json.loads(x) for x in path.read_text().splitlines() if x.strip()])
            merged=nms_ensemble(truth,predictions,overlap=.7)
            write_jsonl(a.output/name/'predictions.jsonl',merged)
            metrics={}
            for model,rows in zip([*members,'ensemble-n-s-nms070'],[*predictions,merged]):
                fixed,_=evaluate_boxes(truth,rows,POLICY); ap=coco_metrics(truth,rows)
                metrics[model]={'fixed':fixed,'coco':ap}
                results.append({'dataset':name,'model':model,'tp':fixed['counts']['tp'],'fp':fixed['counts']['fp'],
                    'fn':fixed['counts']['fn'],'precision025':fixed['precision'],'recall025':fixed['recall'],
                    'small_recall025':fixed['small_box_recall'],'ap50':ap['ap50'],'ap50_95':ap['ap50_95']})
            _write_json(a.output/name/'summary.json',{'members':members,'nms_iou':.7,'score_policy':'uncalibrated max-score pooled candidates',
                'metrics':metrics,'paired_recall_vs_m1n':paired_group_recall_interval(truth,merged,predictions[0]),
                'truth_sha256':dataset['truth_sha256'],'final_evaluation_allowed':False})
        for path,digest in suite['inputs'].items():assert _sha256_file(Path(path))==digest
    for path,digest in inputs.items():assert _sha256_file(Path(path))==digest
    with (a.output/'comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    state.update(status='passed',input_sha256=inputs,recipe='M1-n+M1-s pooled NMS IoU.7',
                 limitation='Opened development data; unlike domains not pooled; no Orin performance measurement')
except BaseException as e:
    state.update(status='failed',error=f'{type(e).__name__}: {e}');raise
finally:_write_json(a.output/'state.json',state)
print(json.dumps({'status':state['status'],'rows':results}))
