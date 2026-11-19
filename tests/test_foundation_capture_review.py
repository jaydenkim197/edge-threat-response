import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_foundation_capture_review import merge, pack, restore, selected_indices, views


class FoundationCaptureTests(unittest.TestCase):
    def test_explicit_selection_is_ordered_unique_and_recording_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'selection.json'
            for indices in ([0,2],[2,0],[0,0],[3],[True]):
                path.write_text(json.dumps({'source_sha256':'source','frame_indices':indices}))
                if indices == [0,2]:
                    self.assertEqual([0,2],selected_indices([{}, {}, {}],'source',path))
                else:
                    with self.assertRaises(ValueError):selected_indices([{}, {}, {}],'source',path)
            with self.assertRaises(ValueError):selected_indices([{}, {}, {}],'wrong',path)

    def test_overlapping_views_cover_all_edges_and_use_smaller_crops(self):
        cuts = views(3840, 2160)
        self.assertEqual(cuts[0], (0, 0, 3840, 2160))
        self.assertEqual(len(cuts), 7)
        for x in range(0, 3840, 31):
            for y in range(0, 2160, 31):
                self.assertTrue(any(a <= x < c and b <= y < d for a,b,c,d in cuts[1:]))
        self.assertLessEqual(max(c-a for a,b,c,d in cuts[1:]), 1536)

    def test_coordinate_restore_preserves_original_space_and_rejects_cut_edges(self):
        self.assertEqual(restore([20, 30, 60, 90], (100, 200, 300, 400), (640, 480)),
                         [120, 230, 160, 290])
        self.assertIsNone(restore([1, 30, 60, 90], (100, 200, 300, 400), (640, 480)))
        self.assertIsNone(restore([20, 30, float('nan'), 90], (0,0,640,480), (640,480)))
        self.assertEqual(restore([0, 0, 30, 30], (0,0,640,480), (640,480)), [0,0,30,30])

    def test_duplicate_views_keep_best_box_and_distinct_objects(self):
        proposals = [{'xyxy':[10,10,30,30], 'confidence':.5},
                     {'xyxy':[11,11,30,30], 'confidence':.8},
                     {'xyxy':[70,50,90,80], 'confidence':.6}]
        self.assertEqual(merge(proposals), [proposals[1], proposals[2]])

    def test_pack_keeps_missed_frames_pending_and_never_overwrites_reviews(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            frames=root/'frames'
            frames.mkdir()
            rows=[]
            for index, color in enumerate(('red','blue')):
                path=frames/f'{index:06d}.jpg'
                Image.new('RGB',(40,30),color).save(path)
                rows.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'width':40,'height':30,'timestamp_s':float(index),
                             'human_review':'pending','training_approved':False})
            (frames/'summary.json').write_text(json.dumps({'frames':2,'width':40,'height':30,
                'source_sha256':'source','sampling':'test'}))
            (frames/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            predictions=root/'predictions.jsonl'
            predictions.write_text(''.join(json.dumps({'frame_index':i,'image_sha256':r['sha256'],
                'timestamp_s':r['timestamp_s'],'proposals':[{'xyxy':[1,2,10,12],'confidence':.4}] if i==0 else []})+'\n'
                for i,r in enumerate(rows)))
            predictions.with_suffix('.meta.json').write_text(json.dumps({'source_sha256':'source'}))
            args=argparse.Namespace(frames=frames,predictions=predictions,
                output=root/'test-session',session_id='test-session',threshold=.2)
            pack(args)
            evidence=[json.loads(line) for line in (root/'review/image-evidence.jsonl').read_text().splitlines()]
            self.assertEqual([r['knife_count'] for r in evidence],[1,0])
            self.assertTrue(all(r['human_review']=='pending' and r['training_approved'] is False for r in evidence))
            prior=(root/'review/image-evidence.jsonl').read_bytes()
            with self.assertRaises(ValueError):
                pack(args)
            self.assertEqual(prior,(root/'review/image-evidence.jsonl').read_bytes())
