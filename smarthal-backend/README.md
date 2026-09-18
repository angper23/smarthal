# SmartHal Backend

A small Flask server that reads the Reolink camera's RTSP stream and re-exposes it as an MJPEG HTTP stream (`/video_feed`) the React app can show with a plain `<img>` tag — browsers can't play RTSP directly. It also reports whether the camera is reachable (`/status`).

This only matters for the **Live Feed** screen. The rest of the app doesn't need it running.

## Run it

### First-time setup

**Step 1 — Install Python.** If you don't already have it, download it from [python.org](https://www.python.org/downloads/) (any recent Python 3 version). This also installs `pip`, the tool used below.

**Step 2 — Move into this folder** (from the project root):
```bash
cd smarthal-backend
```

**Step 3 — Create a virtual environment and install dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
A virtual environment is just an isolated folder for this project's Python packages, so they don't clash with anything else on your machine. You'll need to `source venv/bin/activate` again each time you open a new terminal to work on this — see "Already set up?" below.

**Step 4 — Set the camera's URL:**
```bash
cp .env.example .env
```
Then open `.env` in a text editor and replace the placeholder with the camera's real RTSP URL (ask a teammate for the current IP address and password). This file is gitignored — it stays local to you and is never committed.

**Step 5 — Start the server:**
```bash
python app.py
```
Check it worked by opening `http://localhost:5001/video_feed` directly in a browser — you should see the live camera feed. Leave this running; the frontend (`npm run dev` in the project root) expects it at this address.

To stop the server, click into its terminal and press `Ctrl+C`.

### Already set up?

Every time after the first, you only need:
```bash
cd smarthal-backend
source venv/bin/activate
python app.py
```

## Endpoints

- `GET /video_feed` — the MJPEG stream of the camera feed.
- `GET /status` — `{"camera_online": true|false}`.

## Good to know


- **Why port 5001, not Flask's default 5000?** On macOS, port 5000 is claimed by AirPlay Receiver (System Settings → General → AirDrop & Handoff), so Flask can't bind to it out of the box. Rather than have every teammate disable a system feature, this project just runs on 5001.
- **Live Feed shows video but never detects a face, even with one clearly in frame.** This is a CORS issue, not a face-detection bug — see Troubleshooting below.

## How it works

```
Reolink camera → (RTSP) → this Flask server → (MJPEG over HTTP) → React app's <img> tag
```

Browsers can't speak RTSP (the protocol IP cameras stream over) or play it in an `<img>`/`<video>` tag directly. This server sits in between as a translator: it speaks RTSP to the camera, and re-serves that same video as MJPEG — which is really just "one `.jpg` image, then another, forever" — a format any browser can display in a plain `<img src="...">`.

- **`camera.py`** connects to the camera's RTSP stream on its own background thread, continuously grabbing whatever the newest frame is. This matters because `cv2.VideoCapture.read()` buffers frames internally — without a dedicated thread always draining it, a slow consumer ends up several seconds behind live.
- **`app.py`** is the actual web server. `/video_feed` streams the JPEGs from `camera.py` one after another (throttled to `MJPEG_TARGET_FPS`, currently 10 — no point pushing full camera framerate when the frontend only samples 5x/sec for detection); `/status` just reports whether the camera connection is currently alive.
- Face detection is **not** done here — it still runs client-side in the browser (`face-api.js`, in `LiveFeedScreen.jsx`), reading frames straight off the `<img>` tag that's displaying this stream.

### How camera disconnects are handled

Physically unplugging the camera (or it dropping off the network) was tested directly against the real Reolink hardware. Two things make that reliable:

- **`is_online()` doesn't trust the reader thread's own state** — it just checks how long ago the last real frame arrived (`Camera.STALE_AFTER_SECONDS`, 5s). This matters because `cv2.VideoCapture.read()` can *block* for a long time on a dead connection rather than promptly returning failure — if `/status` waited on that same thread to notice, it'd stay stuck reporting "online" for however long that read happens to hang.
- **The read/open timeouts must be passed into `cv2.VideoCapture(...)` at construction** (see `_open_capture`), not set afterward via `capture.set(...)` — that was tried first and silently ignored, because by the time `.set()` runs, the FFmpeg backend has already opened/probed the stream. Passed at construction, they actually bound how long a stalled connection can hang before the reader loop gives up and retries (tested: dropped a real ~30s recovery time to ~5s).

## Troubleshooting

**Live Feed shows video but never detects a face, even with one clearly in frame.** This is a CORS issue, not a face-detection bug. The backend (port 5001) and the app (port 5173) are different origins, and browsers block face-api.js from reading pixel data off a cross-origin `<img>` unless it explicitly opts in — the failure is silent, so it just looks like detection "isn't working." The fix already lives in `LiveFeedScreen.jsx`: the `<img>` tag has `crossOrigin="anonymous"`, and this server sends the matching `Access-Control-Allow-Origin` header via `flask-cors`. If you ever recreate that `<img>` tag from scratch, remember to keep `crossOrigin="anonymous"` on it.
