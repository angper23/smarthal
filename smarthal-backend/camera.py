"""Reads the Reolink camera's RTSP video stream on a background thread."""

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
        """Start reading from rtsp_url right away. reconnect_delay = seconds between retries."""
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay

        self._capture = None
        self._frame = None
        self._last_frame_time = 0

        # JPEG of the newest frame, shared by every open stream. Encoding a
        # 4K frame costs a lot of CPU, so it's done once per new frame rather
        # than once per viewer per tick — with several streams open, per-
        # viewer encoding starved the reader thread and the camera timed out.
        self._jpeg = None
        self._jpeg_frame_time = 0
        self._encode_lock = threading.Lock()
        self._running = True
        self._lock = threading.Lock()

        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _open_capture(self):
        """Open the RTSP stream with short timeouts. Returns the capture, or None if it fails."""
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
        """Background thread: keep the newest frame, reconnecting whenever the stream drops."""
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
        """Return the newest frame as JPEG bytes, or None if there's no frame yet.

        Each frame is encoded once and the result is shared by every open stream.
        """
        # One encoder at a time: if another stream is already encoding this
        # frame, wait for it and reuse its result instead of encoding again.
        with self._encode_lock:
            with self._lock:
                frame_time = self._last_frame_time
                if self._frame is None:
                    return None
                if frame_time == self._jpeg_frame_time:
                    return self._jpeg
                frame = self._frame.copy()

            ok, buffer = cv2.imencode(".jpg", frame)
            if not ok:
                return None
            self._jpeg = buffer.tobytes()
            self._jpeg_frame_time = frame_time
            return self._jpeg

    def get_frame(self):
        """Return a copy of the newest raw frame (BGR array), or None if there's no frame yet.

        Used by face recognition, which needs pixels rather than JPEG bytes.
        """
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def is_online(self):
        """True if a frame arrived within the last STALE_AFTER_SECONDS (5 seconds)."""
        with self._lock:
            if self._last_frame_time == 0:
                return False
            return (time.time() - self._last_frame_time) < self.STALE_AFTER_SECONDS

    def stop(self):
        """Stop the reader thread and close the camera connection."""
        self._running = False
        if self._capture is not None:
            self._capture.release()
