import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from edge_threat_response.detector_comparison import POLICY, canonical_prediction
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.training import _sha256_file


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comparison_summary', ROOT/'tools/summarize_detector_comparison.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class ComparisonSummaryTests(unittest.TestCase):
    def prepare(self, root, policy):
        def write(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding='utf-8')

        image = {'source_id': 'one', 'frame_index': 0, 'image_sha256': 'a'*64,
                 'source_group': 'one-group', 'width': 100, 'height': 100,
                 'knife_boxes_xyxy': [[10, 10, 30, 30]], 'knife_absence_verified': False}
        truth = {'schema_version': 1, 'status': 'development_authorized', 'partition': 'tuning',
                 'source_group_basis': 'synthetic-test-only', 'images': [image]}
        truth_path = root/'truth.json'
        write(truth_path, truth)
        dataset = {'truth': str(truth_path), 'truth_sha256': _sha256_file(truth_path),
                   'images': 1, 'groups': 1}
        suite = root/'suite.json'
        write(suite, {'datasets': {'tiny': dataset}, 'inputs': {}})
        case = {'id': 'custom-n-640', 'checkpoint_sha256': 'b'*64}
        models = root/'models.json'
        protocol = {'schema_version': 1, 'suite_sha256': _sha256_file(suite),
                    'track': 'ap', 'training_started': False, 'cases': [case]}
        if policy is not None:
            protocol['policy'] = policy
        write(models, protocol)
        predictions = [canonical_prediction(image, [[10, 10, 30, 30]], [.8], [0], 0)[0]]
        fixed, _ = evaluate_boxes(truth, predictions, POLICY)
        run = root/'runs'/'custom-n-640'
        prediction_path = run/'tiny'/'predictions.jsonl'
        prediction_path.parent.mkdir(parents=True)
        prediction_path.write_text(json.dumps(predictions[0])+'\n', encoding='utf-8')
        result = {'status': 'completed_development_comparison', 'suite_sha256': _sha256_file(suite),
                  'models_sha256': _sha256_file(models), 'training_started': False, 'case': case,
                  'environment': {}, 'extra_packages': {}, 'effective_model': {},
                  'script_sha256': 'c'*64, 'git_commit': 'synthetic-test',
                  'results': {'tiny': {'predictions_sha256': _sha256_file(prediction_path),
                                      'truth_sha256': dataset['truth_sha256'], 'fixed': fixed,
                                      'coco': {'ap50': 1.0, 'ap50_95': 1.0}}}}
        write(run/'summary.json', result)
        args = argparse.Namespace(suite=suite, models=models, runs=[root/'runs'], output=root/'aggregate')
        return args, prediction_path

    def test_optional_report_metadata_preserves_frozen_protocol_and_metrics(self):
        for policy in (None, {'prediction_floor': .001}):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as d:
                args, predictions = self.prepare(Path(d), policy)
                before = [_sha256_file(p) for p in (args.models, predictions)]
                summary.summarize(args)
                result = json.loads((args.output/'aggregate.json').read_text())
                self.assertEqual(policy, result['protocol'])
                self.assertEqual(policy is None, result['protocol_metadata_missing'])
                self.assertEqual(1, result['datasets']['tiny']['models']['custom-n-640']['fixed']['recall'])
                self.assertEqual(before, [_sha256_file(p) for p in (args.models, predictions)])

    def test_missing_report_metadata_does_not_bypass_prediction_hash_check(self):
        with tempfile.TemporaryDirectory() as d:
            args, predictions = self.prepare(Path(d), None)
            predictions.write_text('[]\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                summary.summarize(args)
            self.assertFalse(args.output.exists())


if __name__ == '__main__':
    unittest.main()
