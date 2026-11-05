"""Display canonical person/knife detections on the local desktop; save no video."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit

from edge_threat_response.detect_cli import DetectorConfig, _validate_local_weights, build_detector
from edge_threat_response.domain import FrameStatus
from edge_threat_response.jetson_memory import prepare_jetson_memory
from edge_threat_response.media import RTSPFrameSource
from edge_threat_response.training import _git_commit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection', type=Path, required=True)
    parser.add_argument('--detector-config', type=Path, required=True)
    parser.add_argument('--stream', choices=['main', 'sub'], default='main')
    parser.add_argument('--display-width', type=int, default=1280)
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--status-file', type=Path)
    args = parser.parse_args()
    if args.display_width < 320 or (args.max_frames is not None and args.max_frames < 1):
        parser.error('Positive frame limit and display width >=320 required')
    if not os.environ.get('DISPLAY'):
        parser.error('A local desktop DISPLAY is required; do not use SSH X forwarding')

    status = {'status': 'starting', 'displayed_frames': 0, 'stream': args.stream,
              'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_commit': _git_commit(), 'media_saved': False,
              'scope': 'detection preview only; no HOI, event judgment or GPIO'}

    def publish():
        if args.status_file is not None:
            args.status_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.status_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(status, indent=2)+'\n', encoding='utf-8')
            temporary.replace(args.status_file)

    stream = None
    cv2 = None
    try:
        publish()
        config = DetectorConfig.load(args.detector_config)
        _validate_local_weights(config)
        status['native_memory'] = prepare_jetson_memory()
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
        os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'
        os.environ['YOLO_AUTOINSTALL'] = 'false'
        os.environ['ULTRALYTICS_OFFLINE'] = 'true'
        import cv2
        import numpy as np
        cv2.setLogLevel(0)
        private = json.loads(args.connection.read_text(encoding='utf-8-sig'))
        url = urlsplit(private['rtsp_url'])
        if not url.path.endswith(('_main', '_sub')):
            raise ValueError('Unexpected private stream path')
        url = urlunsplit((url.scheme, url.netloc,
                          url.path.rsplit('_', 1)[0]+'_'+args.stream, url.query, ''))
        source = RTSPFrameSource(url, source_id='p430-'+args.stream+'-preview')
        detector = build_detector(config)
        window = 'YOLO26n - Person / Knife - Live CCTV'
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, args.display_width, args.display_width*9//16)
        cv2.moveWindow(window, 80, 80)
        loading = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(loading, 'Connecting camera / loading YOLO26n...', (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2)
        cv2.imshow(window, loading)
        cv2.waitKey(1)
        stream = iter(source)
        clock = time.monotonic()
        last_publish = clock
        count, fps = 0, 0.0
        stop_reason = 'frame_limit'
        for packet in stream:
            result = detector.infer(packet.image)
            if result.status is not FrameStatus.VALID:
                raise RuntimeError('Detector failed; preview stopped')
            height, width = packet.image.shape[:2]
            scale = args.display_width / width
            image = cv2.resize(packet.image, (args.display_width, round(height*scale)))
            counts = Counter(d.label for d in result.detections)
            for detection in result.detections:
                box = detection.bbox
                x1, y1 = round(box.x_min*scale), round(box.y_min*scale)
                x2, y2 = round(box.x_max*scale), round(box.y_max*scale)
                color = (70, 210, 70) if detection.label == 'person' else (0, 130, 255)
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                cv2.putText(image, f'{detection.label} {detection.confidence:.2f}',
                            (max(0, x1), max(65, y1-8)), cv2.FONT_HERSHEY_SIMPLEX,
                            .65, color, 2, cv2.LINE_AA)
            count += 1
            now = time.monotonic()
            if now-clock >= 1:
                fps = count/(now-clock)
                count, clock = 0, now
            cv2.rectangle(image, (0, 0), (image.shape[1], 48), (25, 25, 25), -1)
            label = (f'YOLO26n | {args.stream} | person {counts["person"]}  '
                     f'knife {counts["knife"]} | view {fps:.1f} fps | Q / Esc: close')
            cv2.putText(image, label, (15, 32), cv2.FONT_HERSHEY_SIMPLEX,
                        .7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow(window, image)
            status.update(status='running', displayed_frames=status['displayed_frames']+1,
                          last_detection_counts=dict(counts), view_fps=fps,
                          original_width=width, original_height=height,
                          capture=dict(source.stats))
            if now-last_publish >= 1:
                publish()
                last_publish = now
            key = cv2.waitKey(1) & 0xff
            if key in (ord('q'), ord('Q'), 27):
                stop_reason = 'closed_by_user'
                break
            try:
                visible = cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE)
            except cv2.error:
                visible = -1
            if visible < 1:
                stop_reason = 'closed_by_user'
                break
            if args.max_frames is not None and status['displayed_frames'] >= args.max_frames:
                break
        status.update(status='stopped', stop_reason=stop_reason)
        return 0
    except Exception:
        # Backend exceptions can contain the credential-bearing URL.
        status.update(status='failed', error='Preview failed; inspect private camera/display settings')
        print(status['error'])
        return 2
    finally:
        if cv2 is not None:
            cv2.destroyAllWindows()
        if stream is not None:
            stream.close()
        status['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        publish()


if __name__ == '__main__':
    raise SystemExit(main())
