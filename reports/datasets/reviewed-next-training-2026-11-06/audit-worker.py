from pathlib import Path
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
import sys

ROOT = Path('C:/Class6/edge-threat-response')
SOURCE = Path('C:/Class6/etr-worktrees/e295586')
OUT = ROOT/'data/work/reviewed-next-training-20261106'
sys.path.insert(0, str(SOURCE/'src'))
from edge_threat_response.dataset.review_web import review_verdict
from edge_threat_response.dataset.image_screening import image_signature, similarity_pairs
from edge_threat_response.dataset.development_subset import proxy_components
from edge_threat_response.training import _sha256_file, _write_json


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def family(record_id):
    stem = Path(record_id).stem.lower()
    clean = re.sub(r'\.rf\.[a-f0-9]+$', '', stem)
    if clean == stem:
        return None
    clean = re.sub(r'_(jpg|png|jpeg)$', '', clean)
    return re.sub(r'\d+$', '', clean).rstrip('_- .') or clean


inventory_path = ROOT/'data/processed/raw-real-20261105-v3/inventory.jsonl'
inventory_hash = _sha256_file(inventory_path)
inventory = read_rows(inventory_path)
by_sha = {x['image_sha256']: x for x in inventory}
base = read_rows(ROOT/'data/processed/raw-real-20261105-v2/signatures.jsonl')
pairs = read_rows(ROOT/'data/processed/raw-real-20261105-v2/similarity-pairs.jsonl')
groups = proxy_components(base, pairs)
assert all(groups[x['image_id']] == x['source_group'] for x in inventory)
base_by_sha = defaultdict(list)
families = defaultdict(set)
for row in base:
    base_by_sha[row['image_sha256']].append(row)
    f = family(row['record_id'])
    if f:
        families[f].add(groups[row['record_id']])
protected_groups = {groups[x['record_id']] for x in base if x['dataset_id'] == 'protected'}
protected_groups |= {x['source_group'] for x in inventory if x['split'] in {'val', 'test'}}

config = json.loads((ROOT/'data/review/team-server/config.json').read_text())
all_rows, database_fingerprints = [], {}
dataset_counts = {}
novel_signatures = {}
for entry in config['datasets']:
    if not entry.get('review_dir'):
        continue
    counts = Counter()
    counts['prepared'] = 0
    batches = [{'id': 'initial', 'review_dir': entry['review_dir']}, *entry.get('review_batches', [])]
    for batch in batches:
        pack = Path(batch['review_dir'])
        csv_bytes = (pack/'review.csv').read_bytes()
        evidence_bytes = (pack/'image-evidence.jsonl').read_bytes()
        evidence = [json.loads(x) for x in evidence_bytes.decode('utf-8').splitlines() if x.strip()]
        counts['prepared'] += len(evidence)
        uri = (pack/'human-review.sqlite3').resolve().as_uri()+'?mode=ro'
        with closing(sqlite3.connect(uri, uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            pack_hash = db.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()[0]
            assert pack_hash == hashlib.sha256(csv_bytes+evidence_bytes).hexdigest()
            saved = list(db.execute('SELECT sample,version,payload FROM reviews ORDER BY sample'))
            db.rollback()
        database_fingerprints[entry['id']+'/'+batch['id']] = {
            'pack_hash': pack_hash, 'review_count': len(saved),
            'reviews_sha256': hashlib.sha256(json.dumps(saved, ensure_ascii=False).encode()).hexdigest()}
        for sample, version, payload_text in saved:
            ev = evidence[sample]
            payload = json.loads(payload_text)
            image = (pack/ev['image_file']).resolve()
            assert image.is_relative_to(pack.resolve())
            digest = _sha256_file(image)
            assert digest == ev['image_sha256']
            verdict = review_verdict(payload, ev['knife_count'])
            row = {'dataset': entry['id'], 'batch': batch['id'], 'sample': sample, 'version': version,
                   'image_sha256': digest, 'verdict': verdict, 'domain': payload.get('domain', 'unclear'),
                   'knife_count': ev['knife_count'], 'width': ev['width'], 'height': ev['height'],
                   'boxes': ev['knife_boxes_xyxy_raw'], 'image_path': ev['image_path'],
                   'negative_knife_absence': payload.get('negative_knife_absence'),
                   'review_payload_sha256': hashlib.sha256(payload_text.encode()).hexdigest()}
            counts['reviewed'] += 1
            counts['verdict_'+verdict] += 1
            if verdict == 'ok':
                counts['ok_positive' if ev['knife_count'] else 'ok_negative'] += 1
                counts['ok_domain_'+row['domain']] += 1
                if any((b[2]-b[0])*(b[3]-b[1])/(ev['width']*ev['height']) <= .02 for b in row['boxes']):
                    counts['ok_small_images'] += 1
                if ev['knife_count'] == 0 and row['negative_knife_absence'] == 'yes':
                    counts['ok_negative_absence_confirmed'] += 1
            matched = by_sha.get(digest)
            if matched:
                row['raw_split'] = matched['split']
                row['raw_group'] = matched['source_group']
                row['raw_source'] = matched['source_dataset']
                assert _sha256_file(Path(matched['label'])) == matched['label_sha256']
                boxes = []
                for line in Path(matched['label']).read_text().splitlines():
                    values = line.split()
                    assert len(values) == 5 and values[0] == '0'
                    x, y, w, h = map(float, values[1:])
                    boxes.append(((x-w/2)*ev['width'], (y-h/2)*ev['height'],
                                  (x+w/2)*ev['width'], (y+h/2)*ev['height']))
                row['raw_overlay_matches'] = (len(boxes) == len(row['boxes']) and
                    all(max(abs(a-b) for a,b in zip(left,right)) <= .75
                        for left,right in zip(sorted(boxes), sorted(row['boxes']))))
                row['protection'] = 'protected_group' if matched['source_group'] in protected_groups else 'raw_train'
            elif digest in base_by_sha:
                linked = {groups[x['record_id']] for x in base_by_sha[digest]}
                row['protection'] = 'protected_group' if linked & protected_groups else 'source_import_excluded'
            else:
                row['protection'] = 'not_in_raw_source_cache'
                if digest not in novel_signatures:
                    novel_signatures[digest] = {**image_signature(image, expected_sha256=digest),
                        'record_id': 'review/'+entry['id']+'/'+ev['image_path'],
                        'dataset_id': entry['id'], 'original_split': ev.get('original_split', 'unknown')}
            if verdict == 'ok':
                counts['ok_'+row['protection']] += 1
                if row.get('raw_split') == 'train':
                    counts['ok_raw_train_overlay_match' if row['raw_overlay_matches'] else 'ok_raw_train_overlay_mismatch'] += 1
            all_rows.append(row)
    dataset_counts[entry['id']] = dict(counts)

novel_links = {}
integer_base = [(int(x['dhash64'],16),x) for x in base]
for digest, row in novel_signatures.items():
    linked, near_count = set(), 0
    value = int(row['dhash64'],16)
    for other_value, other in integer_base:
        if (value^other_value).bit_count() <= 4 and similarity_pairs([row,other], 4):
            linked.add(groups[other['record_id']]);near_count += 1
    f = family(row['record_id'])
    if f:
        linked |= families.get(f,set())
    novel_links[digest] = {'protected_link': bool(linked & protected_groups),
                           'direct_near_matches': near_count, 'proxy_groups': sorted(linked)}
for row in all_rows:
    if row['image_sha256'] in novel_links:
        row['novel_links'] = novel_links[row['image_sha256']]

summary = {'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'datasets': dataset_counts,
           'database_snapshots': database_fingerprints, 'raw_inventory_sha256': inventory_hash,
           'raw_train_images': sum(x['split']=='train' for x in inventory),
           'novel_signature_count': len(novel_signatures),
           'near_check_scope': 'direct dHash4 and existing Roboflow-family links to frozen source/holdout groups; no novel-novel transitive approval',
           'training_materialized': False, 'production_review_db_modified': False}
for dataset in dataset_counts:
    selected = [x for x in all_rows if x['dataset']==dataset and x['verdict']=='ok']
    summary['datasets'][dataset]['ok_novel_direct_unprotected'] = sum(
        x['protection']=='not_in_raw_source_cache' and not x['novel_links']['protected_link'] for x in selected)
    summary['datasets'][dataset]['ok_novel_direct_protected'] = sum(
        x['protection']=='not_in_raw_source_cache' and x['novel_links']['protected_link'] for x in selected)
bad_same = {x['image_sha256'] for x in all_rows if x['verdict']!='ok' and x.get('raw_split')=='train' and x['raw_overlay_matches']}
bad_different = {x['image_sha256'] for x in all_rows if x['verdict']!='ok' and x.get('raw_split')=='train' and not x['raw_overlay_matches']}
good_same = {x['image_sha256'] for x in all_rows if x['verdict']=='ok' and x.get('raw_split')=='train' and x['raw_overlay_matches']}
summary.update(reviewed_ok_unique=len({x['image_sha256'] for x in all_rows if x['verdict']=='ok'}),
               raw_train_reviewed_ok_same_overlay=len(good_same),
               raw_train_held_same_overlay=len(bad_same), raw_train_held_different_overlay=len(bad_different),
               raw_train_conflicting_verdict_sha=len(good_same & bad_same))
assert _sha256_file(inventory_path)==inventory_hash
_write_json(OUT/'audit-summary.json',summary)
with (OUT/'review-evidence-snapshot.jsonl').open('x',encoding='utf-8') as f:
    for row in all_rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
print(json.dumps(summary,ensure_ascii=True),flush=True)
