import hashlib,json,sys,subprocess,os,getpass,zipfile
from pathlib import Path
root=Path(r'C:\Class6\edge-threat-response');source=Path(r'C:\Class6\etr-worktrees\m2-parallel-20261107')
node=getpass.getuser().lower()
settings={'pc11':'m2-res960.pc11.json','pc12':'m2-mildaug.pc12.json','pc14':'m2-seed2.pc14.json'}
assert node in settings,node
archive=root/'data/transfer/m2-20261107/m2-real-20261107-v1.zip.part'
sha=lambda path:hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
assert archive.stat().st_size==2482372843
assert sha(archive)=='f391b24372fb14474d4f72b710005e3b7070afbdd6e423f5894aa191e469837e'
dataset=root/'data/processed/m2-real-20261107-v1'
assert not dataset.exists(),'Preserve earlier extracted inputs'
checkpoint=root/'yolo26n.pt'
if checkpoint.exists():assert sha(checkpoint)=='9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef'
with zipfile.ZipFile(archive) as z:
    for info in z.infolist():
        dest=(root/info.filename).resolve()
        assert dest.is_relative_to(dataset) or dest==checkpoint
        if dest==checkpoint and checkpoint.exists():continue
        assert not dest.exists()
        dest.parent.mkdir(parents=True,exist_ok=True)
        with z.open(info) as inp,dest.open('xb') as out:
            import shutil
            shutil.copyfileobj(inp,out)
assert sha(dataset/'inventory.jsonl')=='120a05f7eb48da60ca70bbc2c0fb67a3320ea52ab60a39c55c5af37fcf311f56'
sys.path.insert(0,str(source/'src'))
from edge_threat_response.training_pair import load_plan
from edge_threat_response.raw_training import prepare_suite
from edge_threat_response.training import _sha256_file,validate_training_approval,TrainingConfig,_write_json
plan=source/'configs/training'/settings[node];spec=load_plan(plan)
profiles=root/'data/processed'/(spec['pair_id']+'-profiles')
q=prepare_suite(plan,dataset/'inventory.jsonl',{'n':checkpoint},profiles,'user-directive-20261107-use-pc11-pc12-pc14-parallel',recipes=['RAW-M2-n'])
item=q['queue'][0]
env={**os.environ,'PYTHONPATH':str(source/'src'),'PYTHONIOENCODING':'utf-8','YOLO_AUTOINSTALL':'false'}
logs=root/'runs/parallel-m2-20261107'
for pattern in ('test_raw_training.py','test_m2_profiles.py','test_raw_followup.py'):
    r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern],cwd=source,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (logs/(pattern+'.log')).write_bytes(r.stdout)
    if r.returncode:raise RuntimeError(r.stdout.decode('utf-8','replace'))
r=subprocess.run([sys.executable,'-m','edge_threat_response.training','--config',item['config'],'--data',item['data'],'--dataset-manifest',item['manifest'],'--approval',q['authorization'],'--output-dir',str(root/'runs/training'),'--preflight-only','--require-cuda'],cwd=source,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(logs/'preflight.log').write_bytes(r.stdout)
if r.returncode:raise RuntimeError(r.stdout.decode('utf-8','replace'))
preflight=json.loads(r.stdout.decode('utf-8').strip())
result={'node':node,'status':'prepared_and_cuda_preflight_passed','source_commit':q['git_commit'],'queue':str(profiles/'queue.json'),'queue_sha256':sha(profiles/'queue.json'),'inventory_sha256':sha(dataset/'inventory.jsonl'),'checkpoint_sha256':sha(checkpoint),'draws_per_epoch':q['draws_per_epoch'],'planned_updates':q['planned_updates_each'],'unique_train':item['unique_train'],'arguments':spec['arguments'],'preflight':preflight,'transfer_sha256':'f391b24372fb14474d4f72b710005e3b7070afbdd6e423f5894aa191e469837e'}
_write_json(logs/'prepared.json',result)
print(json.dumps({'node':node,'status':result['status'],'source_commit':q['git_commit'],'queue':result['queue'],'unique_train':item['unique_train'],'imgsz':spec['arguments']['imgsz'],'seed':spec['arguments']['seed']}))
