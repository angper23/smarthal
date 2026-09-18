import os
import time

from dotenv import load_dotenv
from flask import Flask, Response, jsonify
from flask_cors import CORS

from camera import Camera

load_dotenv()

RTSP_URL = os.environ.get("RTSP_URL")
if not RTSP_URL:
    raise RuntimeError(
        "RTSP_URL is not set. Copy .env.example to .env and fill in your "
        "camera's RTSP URL."
    )

app = Flask(__name__)
# Scoped to the frontend's actual origin rather than left wide open — this
# server has no authentication, so anything looser than "only this specific
# origin, from this same machine" widens who can view the camera stream.
CORS(app, origins=["http://localhost:5173"])

camera = Camera(RTSP_URL)

# The frontend only samples 5 frames/sec for face detection, so there's no
# benefit to encoding and sending full camera framerate (the Reolink's 4K
# main stream) — doing so wastes CPU re-encoding frames nobody looks at,
# which was making the reader thread more likely to fall behind and stall
# after a reconnect. Capping output here costs nothing visually and reduces
# that contention.
MJPEG_TARGET_FPS = 10
MJPEG_FRAME_INTERVAL = 1 / MJPEG_TARGET_FPS


def mjpeg_generator():
    while True:
        tick_start = time.time()

        frame = camera.get_jpeg_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )

        elapsed = time.time() - tick_start
        remaining = MJPEG_FRAME_INTERVAL - elapsed
        if remaining > 0:
            time.sleep(remaining)


@app.route("/video_feed")
def video_feed():
    return Response(
        mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/status")
def status():
    return jsonify({"camera_online": camera.is_online()})


if __name__ == "__main__":
    # 127.0.0.1, not 0.0.0.0: this server has no authentication on
    # /video_feed or /status, so it must only ever be reachable from this
    # same machine — not from anyone else on the same WiFi/LAN. The
    # frontend runs on this same machine too, so this doesn't limit
    # anything functional.
    app.run(host="127.0.0.1", port=5001, threaded=True)
