import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_team_review import write_pack
from stage_proposal_refresh import stage,activate
from edge_threat_response.dataset.review_web import ReviewStore


class ProposalRefreshTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        samples=[]
        for i,color in enumerate(('red','green','blue','pink')):
            b=io.BytesIO()
            Image.new('RGB',(20,20),color).save(b,format='PNG')
            samples.append({'bytes':b.getvalue(),'image_path':f'{i}.png','original_split':'pending',
                'timestamp_s':float(i),'source_video_sha256':'source','boxes':[[1,1,4,5]]})
        write_pack('old',samples,{},root=self.root)
        self.old=self.root/'old'
        self.store=ReviewStore(self.old,review_schema='video-box-v1')
        self.fields={'domain':'target_cctv','knife_presence':'yes','reviewed_boxes':[[1,1,4,5]],'reviewer':'QA'}
        self.store.save(0,0,self.fields)
        self.evidence=[json.loads(line) for line in (self.old/'image-evidence.jsonl').read_text().splitlines()]
        self.selection=self.root/'selection.json'
        items=[{'sample':i,'frame_index':i,'image_sha256':self.evidence[i]['image_sha256']} for i in (1,2,3)]
        self.selection.write_text(json.dumps({'pack_hash':self.store.pack_hash,'source_sha256':'source',
            'frame_indices':[1,2,3],'items':items}))
        # The reviewer finishes sample 1 while offline inference is still running.
        self.store.save(1,0,self.fields)
        self.frozen=self.root/'frozen.sqlite3'
        with self.store.connect() as db, closing(sqlite3.connect(self.frozen)) as target:db.backup(target)
        self.predictions=self.root/'predictions.jsonl'
        self.predictions.write_text(''.join(json.dumps({'frame_index':i,'timestamp_s':float(i),
            'image_sha256':self.evidence[i]['image_sha256'],'proposals':[
                {'xyxy':[5,6,10,12],'confidence':.9,'model':'owlv2-large'}]})+'\n' for i in (1,2,3)))
        self.predictions.with_suffix('.meta.json').write_text(json.dumps({'source_sha256':'source',
            'selection_sha256':hashlib.sha256(self.selection.read_bytes()).hexdigest()}))

    def tearDown(self):self.temp.cleanup()

    def test_refresh_keeps_completed_rows_including_reviews_saved_during_inference(self):
        old_bytes=(self.old/'image-evidence.jsonl').read_bytes()
        result=stage(self.old,self.frozen,self.selection,self.predictions,self.root/'new',revision='qa-r1')
        self.assertEqual((2,2,1),(result['preserved_reviewed'],result['updated_pending'],result['reviewed_during_inference_skipped']))
        new=self.root/'new'
        rows=[json.loads(line) for line in (new/'image-evidence.jsonl').read_text().splitlines()]
        self.assertEqual(self.evidence[:2],rows[:2])
        self.assertEqual([[5,6,10,12]],rows[2]['knife_boxes_xyxy_raw'])
        self.assertEqual('qa-r1',rows[2]['proposal_revision'])
        self.assertEqual((self.old/'review.csv').read_bytes(),(new/'review.csv').read_bytes())
        self.assertEqual(old_bytes,(self.old/'image-evidence.jsonl').read_bytes())
        updated=ReviewStore(new,review_schema='video-box-v1')
        self.assertEqual([1,1,0,0],[r['version'] for r in updated.items()])
        for old,newrow in zip(self.evidence,rows):
            self.assertEqual(old['image_sha256'],newrow['image_sha256'])

    def test_mismatched_identity_is_rejected_before_staging(self):
        lines=[json.loads(line) for line in self.predictions.read_text().splitlines()]
        lines[1]['image_sha256']='wrong'
        self.predictions.write_text('\n'.join(json.dumps(row) for row in lines))
        with self.assertRaises(ValueError):stage(self.old,self.frozen,self.selection,self.predictions,self.root/'new',revision='qa')
        self.assertFalse((self.root/'new').exists())

    def test_invalid_bounds_and_incomplete_predictions_are_rejected(self):
        original=self.predictions.read_text()
        rows=[json.loads(line) for line in original.splitlines()]
        rows[1]['proposals'][0]['xyxy']=[1,2,25,30]
        self.predictions.write_text('\n'.join(json.dumps(row) for row in rows))
        with self.assertRaises(ValueError):stage(self.old,self.frozen,self.selection,self.predictions,self.root/'bad-box',revision='qa')
        self.predictions.write_text(original.splitlines()[0])
        with self.assertRaises(ValueError):stage(self.old,self.frozen,self.selection,self.predictions,self.root/'incomplete',revision='qa')

    def activation_fixture(self):
        result=stage(self.old,self.frozen,self.selection,self.predictions,self.root/'new',revision='qa-r1')
        manifest=self.root/'previews/manifest.json'
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({'pack_hash':self.store.pack_hash,'count':4}))
        team=self.root/'team.sqlite3'
        with closing(sqlite3.connect(team)) as db:
            db.execute('CREATE TABLE review_batches(pack,batch,offset,count,pack_hash)')
            db.execute('INSERT INTO review_batches VALUES (?,?,?,?,?)',('pack','initial',0,4,self.store.pack_hash))
            db.execute('CREATE TABLE assignments(pack,sample,user)')
            db.execute('INSERT INTO assignments VALUES (?,?,?)',('pack',2,'QA-owner'))
            db.commit()
        return result,manifest,team

    def test_activation_rebinds_only_fingerprints_and_keeps_ids_owners_and_reviews(self):
        result,manifest,team=self.activation_fixture()
        activate(self.old,self.root/'new',self.root/'archive',team,'pack',manifest)
        updated=ReviewStore(self.old,review_schema='video-box-v1')
        self.assertEqual([1,1,0,0],[r['version'] for r in updated.items()])
        self.assertEqual(result['pack_hash'],updated.pack_hash)
        self.assertEqual(self.store.pack_hash,ReviewStore(self.root/'archive',review_schema='video-box-v1').pack_hash)
        with closing(sqlite3.connect(team)) as db:
            self.assertEqual(result['pack_hash'],db.execute('SELECT pack_hash FROM review_batches').fetchone()[0])
            self.assertEqual([('pack',2,'QA-owner')],list(db.execute('SELECT * FROM assignments')))
        self.assertEqual(result['pack_hash'],json.loads(manifest.read_text())['pack_hash'])

    def test_activation_failure_restores_files_registry_and_preview_manifest(self):
        _,manifest,team=self.activation_fixture()
        original=manifest.read_bytes()
        with patch('stage_proposal_refresh.os.replace',side_effect=OSError('QA injected failure')):
            with self.assertRaises(OSError):activate(self.old,self.root/'new',self.root/'archive',team,'pack',manifest)
        self.assertEqual(self.store.pack_hash,ReviewStore(self.old,review_schema='video-box-v1').pack_hash)
        self.assertTrue((self.root/'new').is_dir())
        self.assertFalse((self.root/'archive').exists())
        self.assertEqual(original,manifest.read_bytes())
        with closing(sqlite3.connect(team)) as db:
            self.assertEqual(self.store.pack_hash,db.execute('SELECT pack_hash FROM review_batches').fetchone()[0])
