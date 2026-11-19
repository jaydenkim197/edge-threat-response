"""Offline pretrained detector proposals; never infer ground truth from a scenario."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time

from prepare_capture_review import existing_frames
from prepare_team_review import write_pack


def views(width, height):
    """Full frame and six overlapping, smaller views; cover all screen edges."""
    tw, th = min(width, math.ceil(width * .40)), min(height, math.ceil(height * .60))
    return [(0, 0, width, height), *[
        (x, y, x + tw, y + th)
        for y in (0, height - th)
        for x in (0, (width - tw) // 2, width - tw)
    ]]


def merge(proposals, threshold=.55):
    from edge_threat_response.detection_evaluation import iou
    from edge_threat_response.domain import BBox

    kept = []
    for item in sorted(proposals, key=lambda row: -row['confidence']):
        if all(iou(BBox(*item['xyxy']), BBox(*prior['xyxy'])) <= threshold for prior in kept):
            kept.append(item)
    return kept


def restore(box, crop, image_size, *, boundary=3):
    x, y, right, bottom = crop
    width, height = image_size
    a, b, c, d = map(float, box)
    if not all(math.isfinite(v) for v in (a, b, c, d)):
        return None
    # A partial object at an internal tile edge is left to the overlapping view.
    if ((x and a < boundary) or (y and b < boundary)
            or (right < width and c > right-x-boundary)
            or (bottom < height and d > bottom-y-boundary)):
        return None
    result = [max(0., a+x), max(0., b+y), min(float(width), c+x), min(float(height), d+y)]
    return [round(v, 2) for v in result] if result[0] < result[2] and result[1] < result[3] else None


def selected_indices(rows, source_hash, path):
    selection = json.loads(path.read_text(encoding='utf-8'))
    indices = selection.get('frame_indices')
    if (selection.get('source_sha256') != source_hash or not isinstance(indices, list) or not indices
            or any(type(index) is not int or not 0 <= index < len(rows) for index in indices)
            or indices != sorted(set(indices))):
        raise ValueError('Selected frames must be unique, ordered and bound to this recording')
    return indices


def predictor(kind, path, contrastive=False):
    if contrastive and kind != 'owlv2-large':
        raise ValueError('Contrastive class selection is supported for OWLv2 only')
    import torch
    if kind == 'coco-yolo-x':
        from ultralytics import YOLO
        model = YOLO(str(path))
        knife_id = next(key for key, value in model.names.items() if value == 'knife')
        def predict(image):
            result = model.predict(image, device=0, imgsz=1280, conf=.03, classes=[knife_id], verbose=False)[0]
            return [(box[:4], box[4]) for box in result.boxes.data.detach().cpu().tolist()]
        return predict
    if kind == 'rf-large':
        from rfdetr import RFDETRLarge
        from rfdetr.assets.coco_classes import COCO_CLASSES
        assert COCO_CLASSES[49] == 'knife'
        model = RFDETRLarge(pretrain_weights=str(path), device='cuda', amp=False)
        def predict(image):
            result = model.predict(image, threshold=.03, include_source_image=False)
            return [(box.tolist(), float(score)) for box, score, label in
                    zip(result.xyxy, result.confidence, result.class_id, strict=True) if label == 49]
        return predict
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    processor = AutoProcessor.from_pretrained(path, local_files_only=True)
    options = {'dtype': torch.float16, 'attn_implementation': 'sdpa'} if kind == 'owlv2-large' else {}
    model = AutoModelForZeroShotObjectDetection.from_pretrained(
        path, local_files_only=True, use_safetensors=True, **options).eval().to('cuda')
    def predict(image):
        if kind == 'grounding-base':
            text = 'knife.'
        else:
            text = [['a knife', 'a toy knife', 'a remote control', 'a mobile phone',
                     'a water bottle', 'tape markings on the floor', 'a person', 'a table']] if contrastive else [['a knife']]
        inputs = processor(images=image, text=text, return_tensors='pt').to('cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
            result = model(**inputs)
        if kind == 'grounding-base':
            record = processor.post_process_grounded_object_detection(
                result, inputs.input_ids, threshold=.03, text_threshold=.15,
                target_sizes=[(image.height, image.width)])[0]
        else:
            record = processor.post_process_grounded_object_detection(
                result, threshold=.03, target_sizes=[(image.height, image.width)])[0]
        found = list(zip(record['boxes'].detach().cpu().tolist(), record['scores'].detach().cpu().tolist(), strict=True))
        if contrastive:
            found = [item for item, label in zip(found, record['labels'].tolist(), strict=True) if label in (0,1)]
        return found
    return predict


def infer(args):
    import torch
    from PIL import Image
    torch.set_num_threads(4)
    torch.set_grad_enabled(False)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU is required for offline proposals')
    frame_summary = json.loads((args.frames/'summary.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (args.frames/'frames.jsonl').read_text(encoding='utf-8').splitlines()]
    indices = list(range(len(rows))) if args.samples == 0 else sorted(set(
        min(len(rows)-1, round((i+.5)*len(rows)/args.samples)) for i in range(args.samples)))
    if getattr(args, 'indices_file', None):
        indices = selected_indices(rows, frame_summary['source_sha256'], args.indices_file)
    assert not args.output.exists(), 'Keep previous predictions unchanged'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    weights = args.model_path/'model.safetensors' if args.model_path.is_dir() else args.model_path
    with weights.open('rb') as handle:
        weight_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
    fn = predictor(args.model, args.model_path, getattr(args, 'contrastive', False))
    started, total_boxes = time.monotonic(), 0
    with args.output.open('x', encoding='utf-8') as stream:
        for number, index in enumerate(indices, 1):
            row = rows[index]
            path = args.frames/row['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
            proposals = []
            with Image.open(path) as source:
                image = source.convert('RGB')
                assert image.size == (row['width'], row['height'])
                regions = views(*image.size) if args.layout == 'tiles' else [(0, 0, *image.size)]
                for view, crop in enumerate(regions):
                    for box, score in fn(image.crop(crop)):
                        restored = restore(box, crop, image.size)
                        if restored is not None and math.isfinite(score):
                            proposals.append({'xyxy': restored, 'confidence': round(float(score), 6),
                                              'view': view, 'model': args.model})
            boxes = merge(proposals)
            total_boxes += len(boxes)
            stream.write(json.dumps({'frame_index': index, 'image_sha256': row['sha256'],
                                     'timestamp_s': row['timestamp_s'], 'proposals': boxes})+'\n')
            stream.flush()
            if number % 20 == 0 or number == len(indices):
                print(json.dumps({'model': args.model, 'done': number, 'total': len(indices),
                                  'elapsed_s': round(time.monotonic()-started, 1), 'raw_boxes': total_boxes}), flush=True)
    meta = {'model': args.model, 'weights_sha256': weight_hash, 'layout': args.layout,
            'source_sha256': frame_summary['source_sha256'], 'frames': len(indices),
            'elapsed_s': round(time.monotonic()-started, 1), 'torch': torch.__version__,
            'gpu': torch.cuda.get_device_name(), 'raw_threshold': .03, 'merge_iou': .55,
            'contrastive': getattr(args, 'contrastive', False),
            'precision': 'float16/sdpa' if args.model == 'owlv2-large' else
                         ('autocast-float16' if args.model == 'grounding-base' else 'float32'),
            'status': 'model proposals only; not human labels'}
    if getattr(args, 'indices_file', None):
        meta['selection_sha256'] = hashlib.sha256(args.indices_file.read_bytes()).hexdigest()
    args.output.with_suffix('.meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')


def pack(args):
    if (not re.fullmatch(r'[a-z0-9-]{1,60}', args.session_id)
            or args.output.name != args.session_id or not 0 <= args.threshold <= 1
            or args.output.exists() or (args.output.parent/'review').exists()):
        raise ValueError('Use a new, valid session/pack directory and probability threshold')
    summary = json.loads((args.frames/'summary.json').read_text(encoding='utf-8'))
    frames = existing_frames(args.frames.resolve(), summary['source_sha256'])
    predictions = [json.loads(line) for line in args.predictions.read_text(encoding='utf-8').splitlines()]
    assert len(predictions) == len(frames)
    assert [row['frame_index'] for row in predictions] == list(range(len(frames)))
    metadata = json.loads(args.predictions.with_suffix('.meta.json').read_text(encoding='utf-8'))
    assert metadata['source_sha256'] == summary['source_sha256']
    counts = {'with_proposals': 0, 'without_proposals': 0, 'proposal_boxes': 0}
    def samples():
        for (image, stamp), prediction in zip(frames, predictions, strict=True):
            raw = image.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == prediction['image_sha256']
            assert stamp == prediction['timestamp_s']
            boxes = [p for p in prediction['proposals'] if p['confidence'] >= args.threshold]
            counts['with_proposals' if boxes else 'without_proposals'] += 1
            counts['proposal_boxes'] += len(boxes)
            yield {'bytes': raw, 'image_path': f'{args.session_id}/{image.name}',
                   'source_id': args.session_id, 'capture_session_id': args.session_id,
                   'timestamp_s': stamp, 'source_video_sha256': summary['source_sha256'],
                   'original_split': 'capture-review-pending', 'boxes': [p['xyxy'] for p in boxes],
                   'box_proposals': boxes, 'human_review': 'pending',
                   'coordinate_status': 'pretrained offline proposals in original pixels; human review pending'}
    result = write_pack(args.session_id, samples(), {'review_schema': 'video-box-v1',
        'capture_session_id': args.session_id, 'source_video_sha256': summary['source_sha256'],
        'foundation_inference': metadata, 'proposal_threshold': args.threshold,
        'sampling': summary['sampling'], 'scenario_note': getattr(args, 'scenario_note', '')},
        root=args.output.parent)
    args.output.rename(args.output.parent/'review')
    output = args.output.parent/'review'
    result.update(counts)
    (output/'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    entry = {'id': args.session_id, 'name': 'P430 2차 촬영 · 칼 검수', 'role': '직접 촬영 CCTV · 2차',
             'note': '사전학습 모델의 박스를 확인·수정합니다. 미검출도 칼 유무를 확인해주세요.',
             'review_schema': 'video-box-v1', 'direct_review': True, 'review_dir': str(output)}
    (output/'catalog-entry.json').write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('infer')
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--model', choices=['grounding-base', 'owlv2-large', 'rf-large', 'coco-yolo-x'], required=True)
    p.add_argument('--model-path', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--samples', type=int, default=24)
    p.add_argument('--indices-file', type=Path, help='Recording-bound explicit subset; preserves original frame indices')
    p.add_argument('--layout', choices=['full', 'tiles'], default='tiles')
    p.add_argument('--contrastive', action='store_true', help='Separate knives from common hard negatives')
    p.set_defaults(run=infer)
    p = sub.add_parser('pack')
    for name in ['frames', 'predictions', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--session-id', required=True)
    p.add_argument('--threshold', type=float, required=True)
    p.add_argument('--scenario-note', default='', help='Unconfirmed capture notes, never labels')
    p.set_defaults(run=pack)
    args = parser.parse_args()
    args.run(args)
