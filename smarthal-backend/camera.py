import threading
import time

import cv2


class Camera:
    """Reads frames from an RTSP stream on a background thread.

    cv2.VideoCapture buffers frames internally, so a caller that reads
    slower than the camera produces frames ends up several seconds behind
    live. Running the read loop on its own thread and always handing out
    the newest frame avoids that lag.
    """

    # If no frame has arrived within this many seconds, treat the camera as
    # offline regardless of what the reader thread thinks — see is_online().
    STALE_AFTER_SECONDS = 5

    def __init__(self, rtsp_url, reconnect_delay=2):
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay

        self._capture = None
        self._frame = None
        self._last_frame_time = 0
        self._running = True
        self._lock = threading.Lock()

        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _open_capture(self):
        # These timeouts only take effect if passed at construction time —
        # setting them via capture.set(...) *after* cv2.VideoCapture(url) is
        # too late, since the FFmpeg backend has already opened/probed the
        # stream by then (this was tried and silently ignored; ffmpeg fell
        # back to its own ~30s default, which made a real disconnect take
        # up to 30s per retry to notice from inside the reader loop).
        capture = cv2.VideoCapture(
            self.rtsp_url,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000,
            ],
        )
        return capture if capture.isOpened() else None

    def _reader_loop(self):
        while self._running:
            if self._capture is None:
                self._capture = self._open_capture()
                if self._capture is None:
                    time.sleep(self.reconnect_delay)
                    continue

            # This call can block far longer than reconnect_delay on a dead
            # RTSP connection — is_online() does not wait on it to know the
            # camera dropped, it just checks how long ago the last frame was.
            ok, frame = self._capture.read()
            if not ok:
                self._capture.release()
                self._capture = None
                time.sleep(self.reconnect_delay)
                continue

            with self._lock:
                self._frame = frame
                self._last_frame_time = time.time()

    def get_jpeg_frame(self):
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()

        if frame is None:
            return None

        ok, buffer = cv2.imencode(".jpg", frame)
        return buffer.tobytes() if ok else None

    def is_online(self):
        with self._lock:
            if self._last_frame_time == 0:
                return False
            return (time.time() - self._last_frame_time) < self.STALE_AFTER_SECONDS

    def stop(self):
        self._running = False
        if self._capture is not None:
            self._capture.release()
