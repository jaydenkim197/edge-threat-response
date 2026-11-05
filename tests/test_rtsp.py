import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from edge_threat_response.media import RTSPFrameSource


class RTSPTests(unittest.TestCase):
    def test_native_capture_allows_camera_startup_longer_than_five_seconds(self):
        class Capture:
            released = False
            def isOpened(self): return True
            def read(self):
                time.sleep(.002)
                return True, object()
            def release(self): self.released = True

        capture = Capture()
        calls = []
        def open_capture(url, backend, parameters):
            calls.append((backend, parameters))
            return capture

        cv2 = SimpleNamespace(VideoCapture=open_capture, setLogLevel=lambda _: None,
                              CAP_FFMPEG=1900, CAP_PROP_OPEN_TIMEOUT_MSEC=53,
                              CAP_PROP_READ_TIMEOUT_MSEC=54)
        with patch.dict('sys.modules', {'cv2': cv2}):
            source = RTSPFrameSource('rtsp://private:secret@example.invalid/path', source_id='test')
            stream = iter(source)
            next(stream)
            stream.close()
        self.assertEqual([(1900, [53, 20000, 54, 5000])], calls)
        self.assertTrue(capture.released)

    def test_latest_frame_queue_is_bounded_and_released(self):
        class Capture:
            released = False
            index = 0
            def isOpened(self): return True
            def read(self):
                time.sleep(.002)
                self.index += 1
                return True, self.index
            def release(self): self.released = True
        capture = Capture()
        source = RTSPFrameSource("rtsp://private:secret@example.invalid/path", source_id="test", capture_factory=lambda: capture)
        stream = iter(source)
        first = next(stream)
        time.sleep(.03)
        last = next(stream)
        stream.close()
        self.assertGreater(last.frame_index, first.frame_index+1)
        self.assertGreater(source.stats["dropped_frames"], 0)
        self.assertEqual(1, source.stats["max_queue_depth"])
        self.assertTrue(capture.released)

    def test_transport_exception_does_not_leak_credentials(self):
        url = "rtsp://private:very-secret@example.invalid/path"
        def fail(): raise RuntimeError(url)
        source = RTSPFrameSource(url, source_id="test", capture_factory=fail)
        with self.assertRaises(RuntimeError) as raised:
            next(iter(source))
        self.assertNotIn("very-secret", str(raised.exception))
        self.assertNotIn(url, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
