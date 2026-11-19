"""Stage pending-only proposals against a frozen review DB; never edit live judgments."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def stage(pack, frozen_db, selection_path, predictions_path, output, *, revision, threshold=.15):
    pack, output = pack.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(pack) or not 0 <= threshold <= 1:
        raise ValueError('Use a new staging directory outside the live pack')
    csv = (pack/'review.csv').read_bytes()
    evidence_bytes = (pack/'image-evidence.jsonl').read_bytes()
    old_hash = hashlib.sha256(csv+evidence_bytes).hexdigest()
    rows = [json.loads(line) for line in evidence_bytes.splitlines()]
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    meta = json.loads(predictions_path.with_suffix('.meta.json').read_text(encoding='utf-8'))
    if (selection['pack_hash'] != old_hash or meta['source_sha256'] != selection['source_sha256']
            or meta['selection_sha256'] != digest(selection_path)):
        raise ValueError('Selection, source and inference are not bound to the live pack')
    selected = {item['frame_index']:item for item in selection['items']}
    if len(selected) != len(selection['items']) or sorted(selected) != selection['frame_indices']:
        raise ValueError('Invalid selected frame identities')
    predictions = [json.loads(line) for line in predictions_path.read_text(encoding='utf-8').splitlines()]
    if [row['frame_index'] for row in predictions] != sorted(selected):
        raise ValueError('Missing or reordered predictions')
    with closing(sqlite3.connect(f'{frozen_db.resolve().as_uri()}?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Frozen DB integrity failure')
        if db.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()[0] != old_hash:
            raise ValueError('Frozen DB belongs to another pack')
        reviewed = {row[0] for row in db.execute('SELECT sample FROM reviews')}
    if any(type(item['sample']) is not int or not 0 <= item['sample'] < len(rows) for item in selected.values()):
        raise ValueError('Selected sample outside pack')
    if len({item['sample'] for item in selected.values()}) != len(selected):
        raise ValueError('Repeated sample selection')
    updated, skipped, proposal_boxes, with_boxes = [], [], 0, 0
    for prediction in predictions:
        item = selected[prediction['frame_index']]
        sample = item['sample']
        old = rows[sample]
        if (old['image_sha256'] != item['image_sha256'] or old['image_sha256'] != prediction['image_sha256']
                or old['timestamp_s'] != prediction['timestamp_s']
                or old['source_video_sha256'] != selection['source_sha256']):
            raise ValueError('Image/timestamp identity changed')
        if sample in reviewed:
            skipped.append(sample)
            continue
        proposals = [p for p in prediction['proposals'] if p['confidence'] >= threshold]
        for p in proposals:
            x1,y1,x2,y2 = p['xyxy']
            if (not all(math.isfinite(v) for v in (x1,y1,x2,y2,p['confidence']))
                    or not 0 <= x1 < x2 <= old['width'] or not 0 <= y1 < y2 <= old['height']):
                raise ValueError('Invalid proposal bounds')
        rows[sample] = {**old, 'knife_count':len(proposals),
                        'knife_boxes_xyxy_raw':[p['xyxy'] for p in proposals], 'box_proposals':proposals,
                        'proposal_revision':revision, 'human_review':'pending', 'training_approved':False,
                        'coordinate_status':'OWLv2 offline proposal refresh; original pixels; human review pending'}
        updated.append(sample)
        proposal_boxes += len(proposals)
        with_boxes += bool(proposals)
    pending = set(range(len(rows)))-reviewed
    if set(updated) != pending:
        raise ValueError('Selection does not cover every currently unreviewed sample')
    output.mkdir(parents=True)
    for row in rows:
        source = (pack/row['image_file']).resolve()
        if not source.is_relative_to(pack) or digest(source) != row['image_sha256']:
            raise ValueError('Source image changed or escapes pack')
        target = output/row['image_file']
        target.parent.mkdir(parents=True,exist_ok=True)
        try:
            os.link(source,target)
        except OSError:
            shutil.copy2(source,target)
    (output/'review.csv').write_bytes(csv)
    new_evidence = b''.join((json.dumps(row)+'\n').encode() for row in rows)
    (output/'image-evidence.jsonl').write_bytes(new_evidence)
    new_hash = hashlib.sha256(csv+new_evidence).hexdigest()
    with closing(sqlite3.connect(f'{frozen_db.resolve().as_uri()}?mode=ro',uri=True)) as origin:
        with closing(sqlite3.connect(output/'human-review.sqlite3')) as target:
            origin.backup(target)
            with target:
                target.execute("UPDATE metadata SET value=? WHERE key='pack_hash'",(new_hash,))
            if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Staged database integrity failure')
            for table in ('reviews','history'):
                before = list(origin.execute(f'SELECT * FROM {table} ORDER BY 1'))
                after = list(target.execute(f'SELECT * FROM {table} ORDER BY 1'))
                if before != after:
                    raise ValueError('Judgment/history preservation failure')
    old_summary=json.loads((pack/'summary.json').read_text(encoding='utf-8'))
    identity={key:old_summary[key] for key in ('capture_session_id','source_video_sha256','review_schema') if key in old_summary}
    report = {**identity, 'revision':revision, 'images':len(rows), 'previous_pack_hash':old_hash, 'pack_hash':new_hash,
              'previous_summary_sha256':digest(pack/'summary.json'),
              'knife_objects':sum(row['knife_count'] for row in rows),
              'image_bytes':sum(row['image_bytes'] for row in rows),
              'proposal_scope':'mixed raw proposals: completed evidence preserved; pending rows refreshed',
              'inference_selection':len(selected), 'preserved_reviewed':len(reviewed), 'updated_pending':len(updated),
              'reviewed_during_inference_skipped':len(skipped), 'pending_with_proposals':with_boxes,
              'pending_without_proposals':len(updated)-with_boxes, 'new_proposal_boxes':proposal_boxes,
              'sample_ids_images_and_timestamps_preserved':True, 'review_and_history_rows_preserved':True,
              'inference':meta, 'training_approved':False}
    (output/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for name in ('catalog-entry.json','similarity.jsonl'):
        if (pack/name).is_file(): shutil.copy2(pack/name,output/name)
    return report


def activate(pack, staged, archive, team_db, pack_id, preview_manifest):
    """Call only with the review service stopped and a consistent backup saved."""
    pack, staged, archive, preview_manifest = (p.resolve() for p in (pack,staged,archive,preview_manifest))
    if (pack.parent != staged.parent or pack.parent != archive.parent or archive.exists()
            or pack == staged or preview_manifest.parent.parent != pack.parent):
        raise ValueError('Revision moves must remain inside the capture directory')
    report=json.loads((staged/'summary.json').read_text(encoding='utf-8'))
    def fingerprint(folder):
        return hashlib.sha256((folder/'review.csv').read_bytes()+(folder/'image-evidence.jsonl').read_bytes()).hexdigest()
    old_hash,new_hash=report['previous_pack_hash'],report['pack_hash']
    if fingerprint(pack)!=old_hash or fingerprint(staged)!=new_hash:
        raise ValueError('Pack changed after staging')
    old_manifest=preview_manifest.read_bytes()
    manifest=json.loads(old_manifest)
    if manifest['pack_hash']!=old_hash or manifest['count']!=report['images']:
        raise ValueError('Preview identity mismatch')
    with closing(sqlite3.connect(f"{(pack/'human-review.sqlite3').as_uri()}?mode=ro",uri=True)) as live:
        with closing(sqlite3.connect(f"{(staged/'human-review.sqlite3').as_uri()}?mode=ro",uri=True)) as new:
            if live.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()[0]!=old_hash:
                raise ValueError('Live database fingerprint changed')
            for table in ('reviews','history'):
                if list(live.execute(f'SELECT * FROM {table} ORDER BY 1'))!=list(new.execute(f'SELECT * FROM {table} ORDER BY 1')):
                    raise ValueError('Judgments changed after the frozen snapshot; restage')
            if new.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()[0]!=new_hash:
                raise ValueError('Staged DB fingerprint mismatch')
    archived=active=False
    temporary=None
    with closing(sqlite3.connect(team_db)) as connection:
        connection.execute('BEGIN IMMEDIATE')
        expected=[('initial',0,report['images'],old_hash)]
        actual=list(connection.execute('SELECT batch,offset,count,pack_hash FROM review_batches WHERE pack=? ORDER BY offset',(pack_id,)))
        if actual!=expected:
            connection.rollback()
            raise ValueError('Unexpected registered batch identity')
        try:
            pack.rename(archive)
            archived=True
            staged.rename(pack)
            active=True
            manifest['pack_hash']=new_hash
            with tempfile.NamedTemporaryFile('wb',dir=preview_manifest.parent,delete=False) as file:
                temporary=Path(file.name)
                file.write(json.dumps(manifest,indent=2).encode())
            os.replace(temporary,preview_manifest)
            changed=connection.execute("UPDATE review_batches SET pack_hash=? WHERE pack=? AND batch='initial' AND pack_hash=?",
                                       (new_hash,pack_id,old_hash)).rowcount
            if changed!=1:raise ValueError('Unexpected registry update count')
            connection.commit()
        except Exception:
            connection.rollback()
            if active:pack.rename(staged)
            if archived:archive.rename(pack)
            preview_manifest.write_bytes(old_manifest)
            raise
        finally:
            if temporary and temporary.exists():temporary.unlink()
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pack','frozen-db','selection','predictions','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--revision',required=True)
    args=parser.parse_args()
    print(json.dumps(stage(args.pack,args.frozen_db,args.selection,args.predictions,args.output,revision=args.revision)))
