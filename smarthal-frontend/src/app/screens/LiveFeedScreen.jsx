// Live Feed screen — the main feature of SmartHal
// Streams the Reolink camera via the Flask backend (see /smarthal-backend)
// and shows who's in view: the backend recognizes faces against registered
// residents (GET /recognitions), and this screen draws a box around each one
// on a canvas overlay — green with the resident's name, orange for Unknown,
// red if a resident's face looks like a photo or screen (liveness check).
// Styling is plain on purpose; Collin owns the design.
import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, Circle, AlertTriangle, RefreshCw } from "lucide-react";
import { apiFetch, BACKEND_URL, NetworkError } from "../api.js";

// How often to ask the backend who's in view (it updates ~3 times a second)
const RECOGNITION_POLL_MS = 400;

// How each kind of face is drawn. status comes from the backend: a resident's
// name is only shown once the liveness check says it's a real person
const FACE_STYLES = {
  resident: { color: "#16a34a" },                                     // green, resident's name
  unknown: { color: "#ea580c", label: "Unknown" },                    // orange
  too_far: { color: "#ea580c", label: "Unknown (come closer)" },      // too small to check
  checking: { color: "#64748b", label: "Checking…" },                 // slate, deciding real vs photo
  spoof: { color: "#dc2626", label: "Unknown (possible photo)" },     // red, looked like a photo/screen
  unverified: { color: "#64748b", label: "Unverified" },              // liveness check not working
};

/** Short summary of the faces in view, e.g. "Jordan", "Unknown person", "Jordan + 1 unknown". */
function describeFaces(faces) {
  if (faces.length === 0) return "No Face Detected";
  if (faces.some((f) => f.status === "spoof")) return "Possible photo or screen!";
  const names = faces.filter((f) => f.name).map((f) => f.name);
  const checking = faces.filter((f) => f.status === "checking").length;
  const unknown = faces.length - names.length - checking;
  const parts = [...new Set(names)];
  if (checking) parts.push("Checking…");
  if (unknown) parts.push(parts.length ? `${unknown} unknown` : unknown === 1 ? "Unknown person" : `${unknown} unknown people`);
  return parts.join(" + ");
}

// How often to check whether the backend can still reach the camera
const STATUS_POLL_INTERVAL_MS = 8000;

/** Live Feed screen (/live-feed): the camera stream with resident recognition. */
export function LiveFeedScreen() {
  const navigate = useNavigate();

  // Ref to the <img> showing the backend's MJPEG stream — its size sets the canvas size
  const imgRef = useRef(null);

  // Ref to the canvas element — used to draw bounding boxes on top of the video
  const canvasRef = useRef(null);

  // Whether the <img> failed to load the backend's video stream at all
  // (e.g. the Flask backend isn't running). Mirrored in a ref so the status
  // poll below can see the latest value without restarting its interval
  const [streamError, setStreamErrorState] = useState(false);
  const streamErrorRef = useRef(false);
  // Update streamError in both places: state (redraws the page) and the ref (read by the status poll)
  const setStreamError = useCallback((value) => {
    streamErrorRef.current = value;
    setStreamErrorState(value);
  }, []);

  // Whether the last /status poll couldn't reach the backend at all
  const [backendUnreachable, setBackendUnreachable] = useState(false);

  // URL for the <img> — the video feed plus a short-lived stream token,
  // since an <img> can't send the Authorization header. null until fetched
  const [streamSrc, setStreamSrc] = useState(null);

  // Whether the backend reports the camera itself as reachable — polled
  // from /status rather than inferred from the browser (SRS NFR §5.1)
  const [cameraOnline, setCameraOnline] = useState(true);

  // Faces currently in view, from the backend: [{ box: [x, y, w, h] as
  // fractions of the frame, name (null = Unknown), resident_id, score }]
  const [faces, setFaces] = useState([]);

  // Set if the backend says recognition isn't working (e.g. face models missing)
  const [recognitionError, setRecognitionError] = useState(null);

  // Open (or re-open) the video stream. Stream tokens are single-use and
  // expire after 60 seconds, so every connect fetches a fresh one
  const connectStream = useCallback(async () => {
    try {
      const res = await apiFetch("/stream-token", { method: "POST" });
      if (!res.ok) return; // a 401 has already logged us out
      const { stream_token } = await res.json();
      setStreamError(false);
      setStreamSrc(`${BACKEND_URL}/video_feed?stream_token=${encodeURIComponent(stream_token)}`);
    } catch (err) {
      if (!(err instanceof NetworkError)) throw err;
      setStreamError(true);
    }
  }, [setStreamError]);

  // Open the stream when the screen first loads
  useEffect(() => {
    connectStream();
  }, [connectStream]);

  // Poll the backend's /status endpoint to know if it can still reach the
  // camera — separate from streamError, which only tells us whether the
  // browser's <img> request itself failed. A 401 here (session expired)
  // logs out via apiFetch
  useEffect(() => {
    let cancelled = false;

    // One status check: update online/offline, and reconnect the stream if it had dropped
    const pollStatus = () => {
      apiFetch("/status")
        .then(async (res) => {
          if (cancelled || !res.ok) return;
          const data = await res.json();
          if (cancelled) return;
          setBackendUnreachable(false);
          setCameraOnline(Boolean(data.camera_online));
          // Backend is reachable again after the stream dropped — reconnect
          if (streamErrorRef.current) connectStream();
        })
        .catch((err) => {
          if (!cancelled && err instanceof NetworkError) setBackendUnreachable(true);
        });
    };

    pollStatus();
    const statusInterval = setInterval(pollStatus, STATUS_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(statusInterval);
    };
  }, [connectStream]);

  // Ask the backend who's in view, a few times a second, while the stream is showing.
  // Recognition runs on the backend (it has the residents' saved face angles); the
  // backend pauses it on its own once nobody is asking
  useEffect(() => {
    if (!streamSrc || streamError) return;
    let cancelled = false;
    let busy = false;
    const poll = async () => {
      if (busy) return; // don't stack requests if one is slow
      busy = true;
      try {
        const res = await apiFetch("/recognitions");
        if (cancelled || !res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setFaces(data.faces || []);
        setRecognitionError(data.error || null);
      } catch (err) {
        if (!(err instanceof NetworkError)) throw err; // status poll shows "server unreachable"
      } finally {
        busy = false;
      }
    };
    poll();
    const id = setInterval(poll, RECOGNITION_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
      setFaces([]);
    };
  }, [streamSrc, streamError]);

  // Draw a box (and name label) around each face whenever the results change
  useEffect(() => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;
    // Canvas uses the video's own pixel size; CSS stretches both the same way
    const width = img?.naturalWidth || canvas.width;
    const height = img?.naturalHeight || canvas.height;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, width, height);
    if (!img?.naturalWidth) return;

    const line = Math.max(2, Math.round(height / 240));
    const fontSize = Math.max(14, Math.round(height / 28));
    ctx.font = `600 ${fontSize}px sans-serif`;
    ctx.textBaseline = "top";

    faces.forEach(({ box, name, status }) => {
      const [x, y, w, h] = [box[0] * width, box[1] * height, box[2] * width, box[3] * height];
      const style = FACE_STYLES[status] || FACE_STYLES[name ? "resident" : "unknown"];
      const color = style.color;
      ctx.strokeStyle = color;
      ctx.lineWidth = line;
      ctx.strokeRect(x, y, w, h);

      // Name tag above the box (inside the top edge if there's no room above)
      const label = name || style.label || "Unknown";
      const pad = Math.round(fontSize * 0.3);
      const tagW = ctx.measureText(label).width + pad * 2;
      const tagH = fontSize + pad * 2;
      const tagY = y - tagH >= 0 ? y - tagH : y;
      ctx.fillStyle = color;
      ctx.fillRect(x - line / 2, tagY, tagW, tagH);
      ctx.fillStyle = "white";
      ctx.fillText(label, x - line / 2 + pad, tagY + pad);
    });
  }, [faces]);

  const summary = describeFaces(faces);
  const anyUnknown = faces.some((f) => !f.name);
  const livenessBroken = recognitionError?.startsWith("Liveness");

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header with back button and LIVE badge */}
      <div className="bg-white border-b-2 border-gray-300 p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-gray-100 rounded">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-2xl">Live Feed</h1>
        {/* Pulsing LIVE badge to indicate the camera is active */}
        <span className="ml-auto flex items-center gap-1 bg-red-100 text-red-700 px-2 py-0.5 rounded text-sm animate-pulse">
          <Circle className="w-2 h-2 fill-red-600 text-red-600" />
          LIVE
        </span>
      </div>

      <div className="p-4 space-y-4">

        {/* Status bar — shows camera online and current detection result */}
        <div className="bg-white border-2 border-gray-300 rounded-lg p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Circle
              className={`w-3 h-3 ${
                cameraOnline && !backendUnreachable ? "fill-green-600 text-green-600" : "fill-red-600 text-red-600"
              }`}
            />
            <span className="text-sm">
              {backendUnreachable ? "Server Unreachable" : cameraOnline ? "Camera Online" : "Camera Offline"}
            </span>
          </div>
          <div className="text-sm">
            {/* Who's in view right now, from the backend's recognition */}
            {recognitionError && !livenessBroken ? (
              <span className="text-red-600">Recognition unavailable</span>
            ) : (
              <span className={anyUnknown ? "text-orange-600 font-medium" : faces.length ? "text-green-700 font-medium" : "text-gray-600"}>
                {summary}
              </span>
            )}
          </div>
        </div>

        {/* Error message shown if the browser can't reach the stream at all
            (e.g. the Flask backend isn't running) */}
        {(streamError || backendUnreachable) && (
          <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-red-800">Can't reach the server</p>
              <p className="text-sm text-red-700 mt-1">
                Make sure the SmartHal backend is running locally (see{" "}
                <code>README.md</code>, section 3). This page reconnects
                automatically once it's back.
              </p>
            </div>
            <button
              onClick={connectStream}
              className="flex items-center gap-1 text-sm text-red-700 border border-red-300 rounded px-2 py-1 hover:bg-red-100"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          </div>
        )}

        {/* Error message shown if the backend is up but the camera itself isn't */}
        {!streamError && !backendUnreachable && !cameraOnline && (
          <div className="bg-orange-50 border-2 border-orange-300 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-orange-800">Camera unreachable</p>
              <p className="text-sm text-orange-700 mt-1">
                The backend can't reach the camera. Check its power and network connection.
              </p>
            </div>
          </div>
        )}

        {/* Shown if the backend can't run recognition (e.g. face models not downloaded) */}
        {recognitionError && !streamError && !backendUnreachable && (
          <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
            <div className="flex-1">
              {livenessBroken ? (
                <>
                  <p className="font-medium text-red-800">The photo check isn't working</p>
                  <p className="text-sm text-red-700 mt-1">
                    Residents' names are hidden until it's fixed, so a photo can't pass as a resident.
                    Check that <code>smarthal-backend/liveness_models/</code> has its two model files, then
                    restart the backend.
                  </p>
                </>
              ) : (
                <>
                  <p className="font-medium text-red-800">Face recognition isn't working</p>
                  <p className="text-sm text-red-700 mt-1">
                    The video still works. On the backend computer, run <code>python faces.py</code> in{" "}
                    <code>smarthal-backend</code> to download the face models, then restart the backend.
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {/* Camera stream + canvas overlay — only shown if the stream itself loaded */}
        {!streamError && (
          <div className="bg-white border-2 border-gray-300 rounded-lg overflow-hidden">
            <div className="relative aspect-video bg-black">

              {/* MJPEG stream served by the Flask backend (see /smarthal-backend).
                  Faces are recognized on the backend, so the browser never reads
                  pixels off this image. crossOrigin stays so that can be added back
                  without surprises, and it must come BEFORE src: React sets
                  attributes in this order, and if src lands first, Safari starts a
                  non-CORS request and restarts it once crossOrigin appears —
                  opening the stream twice for every connect */}
              {streamSrc && (
                <img
                  ref={imgRef}
                  crossOrigin="anonymous"
                  src={streamSrc}
                  alt="Live camera feed"
                  className="w-full h-full object-cover"
                  onError={() => setStreamError(true)}
                />
              )}

              {/* Canvas sits on top of the stream — bounding boxes are drawn here */}
              <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full"
              />
            </div>

            {/* Footer showing camera info and detection badge */}
            <div className="p-4 border-t-2 border-gray-300 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Resolution: 1080p</p>
                <p className="text-sm text-gray-600">Location: Main Entrance</p>
              </div>
              {/* Who's in view — orange if anyone is Unknown, green if only residents */}
              <div
                className={`px-3 py-1 rounded-full text-sm font-medium border-2 ${
                  anyUnknown
                    ? "bg-orange-50 text-orange-700 border-orange-300"
                    : "bg-green-50 text-green-700 border-green-300"
                }`}
              >
                {summary}
              </div>
            </div>
          </div>
        )}

        {/* Back to dashboard button */}
        <button
          onClick={() => navigate("/dashboard")}
          className="w-full py-3 bg-gray-800 text-white rounded border-2 border-gray-800 hover:bg-gray-700"
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}
