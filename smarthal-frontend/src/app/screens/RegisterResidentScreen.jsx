// Register Resident screen — adds a known person using five webcam photos
// (front, left, right, up, down), so the live camera can later recognize them
// from different angles. face-api.js checks there's exactly one face before
// each photo is taken; the backend (POST /residents) checks every photo again,
// computes the face embeddings and saves them.
// Styled with Collin's theme (colors in styles/theme.css); Collin owns the design.
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import * as faceapi from "face-api.js";
import { ArrowLeft, Camera, CheckCircle, AlertTriangle, RefreshCw, Trash2 } from "lucide-react";
import { apiFetch, NetworkError } from "../api.js";

// Same face detection model the Live Feed screen uses
const MODEL_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model";

// The five photos, in capture order. `angle` must match the backend's RESIDENT_ANGLES
const STEPS = [
  { angle: "front", label: "Front", prompt: "Look straight at the camera" },
  { angle: "left", label: "Left", prompt: "Turn your head slightly to your left" },
  { angle: "right", label: "Right", prompt: "Turn your head slightly to your right" },
  { angle: "up", label: "Up", prompt: "Tilt your chin up a little" },
  { angle: "down", label: "Down", prompt: "Tilt your chin down a little" },
];
const ANGLES = STEPS.map((s) => s.angle);

// Check for a face 4 times a second; take the photo once exactly one face has
// been in view for 12 checks in a row (3 s), so the person has time to settle
const DETECT_INTERVAL_MS = 250;
const HOLD_TICKS = 12;

// After each photo, pause so the person can turn before the next one is taken
const PAUSE_AFTER_SHOT_MS = 1500;

/**
 * The oval the resident lines their face up with, in the video's own pixel
 * coordinates. Sized from the video height so it fits any webcam shape.
 */
function faceGuide(width, height) {
  const ry = height * 0.36;
  return { cx: width / 2, cy: height * 0.46, rx: ry * 0.78, ry };
}

// Direction arrows drawn beside the oval for each angle. side: -1 = left of the
// oval, 1 = right; rotate: degrees from pointing right. The preview is mirrored
// like a selfie camera, so "turn to your left" points to the screen's left
const TURN_ARROWS = {
  front: [],
  left: [{ side: -1, rotate: 180 }],
  right: [{ side: 1, rotate: 0 }],
  up: [{ side: -1, rotate: -90 }, { side: 1, rotate: -90 }],
  down: [{ side: -1, rotate: 90 }, { side: 1, rotate: 90 }],
};

/** SVG path for an arrow of size s centered on (0, 0), pointing right. */
function arrowPath(s) {
  const h = s / 2;
  return `M ${-h} ${-s * 0.15} L ${s * 0.1} ${-s * 0.15} L ${s * 0.1} ${-s * 0.4} L ${h} 0 `
    + `L ${s * 0.1} ${s * 0.4} L ${s * 0.1} ${s * 0.15} L ${-h} ${s * 0.15} Z`;
}

/**
 * How well a detected face box sits in the guide oval:
 * "ok", "off" (not centered in the oval), "far" (too small) or "close" (too big).
 * Lenient on purpose: the face shifts a bit when the resident turns for the side angles.
 */
function faceAlignment(box, guide) {
  const fx = box.x + box.width / 2;
  const fy = box.y + box.height / 2;
  const dx = (fx - guide.cx) / guide.rx;
  const dy = (fy - guide.cy) / guide.ry;
  if (dx * dx + dy * dy > 0.45 * 0.45) return "off";
  // The detector's box runs roughly brow to chin, so a face filling the oval is ~55-70% of its height
  const fill = box.height / (2 * guide.ry);
  if (fill < 0.35) return "far";
  if (fill > 0.9) return "close";
  return "ok";
}

/** Turn a getUserMedia error into a message the user can act on. */
function cameraErrorMessage(err) {
  if (err?.name === "NotAllowedError") {
    return "Camera access was blocked. Allow the camera for this site in your browser settings, then try again.";
  }
  if (err?.name === "NotFoundError") return "No camera was found on this device.";
  if (err?.name === "NotReadableError") return "The camera is being used by another app. Close it and try again.";
  return "Couldn't start the camera. Try again.";
}

/** Register Resident screen (/register-resident). */
export function RegisterResidentScreen() {
  const navigate = useNavigate();

  const [residentName, setResidentName] = useState("");

  // "form" → "capturing" → "review" → "saving" → "done"
  const [phase, setPhase] = useState("form");

  // Captured photos: { front: { blob, url }, left: ..., ... }
  const [shots, setShots] = useState({});

  // Which angle is being captured right now, and whether this is a single
  // retake (go back to review afterwards) rather than the full sequence
  const [target, setTarget] = useState("front");
  const [retaking, setRetaking] = useState(false);

  // Camera + face detection status shown under the preview
  const [camError, setCamError] = useState(null);
  const [camReady, setCamReady] = useState(false);
  const [faceStatus, setFaceStatus] = useState("waiting"); // waiting | none | one | many
  const [alignment, setAlignment] = useState(null); // ok | off | far | close (when one face)
  const [videoSize, setVideoSize] = useState(null); // { w, h } of the webcam image, for the guide oval
  const [hold, setHold] = useState(0);
  const [justCaptured, setJustCaptured] = useState(false);
  const [modelsReady, setModelsReady] = useState(faceapi.nets.tinyFaceDetector.isLoaded);
  const [modelError, setModelError] = useState(false);

  // Backend rejection: { message, angle? } — angle highlights the photo to retake
  const [saveError, setSaveError] = useState(null);
  const [saved, setSaved] = useState(null);

  // Already-registered residents (GET /residents), shown under the form with Delete buttons
  const [residents, setResidents] = useState(null);
  const [listError, setListError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const pauseUntilRef = useRef(0);

  // Refs mirror state the detection loop reads, so the loop doesn't restart on every change
  const targetRef = useRef(target);
  const retakingRef = useRef(retaking);
  const shotsRef = useRef(shots);
  targetRef.current = target;
  retakingRef.current = retaking;
  shotsRef.current = shots;

  // Download the face detector (skipped if Live Feed already loaded it)
  useEffect(() => {
    if (modelsReady) return;
    let cancelled = false;
    faceapi.nets.tinyFaceDetector
      .loadFromUri(MODEL_URL)
      .then(() => !cancelled && setModelsReady(true))
      .catch(() => !cancelled && setModelError(true));
    return () => {
      cancelled = true;
    };
  }, [modelsReady]);

  // Load the list of registered residents
  const loadResidents = useCallback(async () => {
    try {
      const res = await apiFetch("/residents");
      if (!res.ok) return; // 401 already handled by apiFetch
      setResidents((await res.json()).residents);
      setListError(null);
    } catch (err) {
      setListError(err instanceof NetworkError ? "Can't reach the server." : "Couldn't load residents.");
    }
  }, []);

  useEffect(() => {
    loadResidents();
  }, [loadResidents]);

  // Delete a resident (and their photos) after confirming
  const handleDelete = async (resident) => {
    if (!window.confirm(`Delete ${resident.name}? Their face photos will be removed and they'll no longer be recognized.`)) return;
    setDeletingId(resident.id);
    setListError(null);
    try {
      const res = await apiFetch(`/residents/${resident.id}`, { method: "DELETE" });
      if (res.status === 204 || res.status === 404) {
        setResidents((list) => list.filter((r) => r.id !== resident.id));
      } else if (res.status !== 401) {
        const data = await res.json().catch(() => ({}));
        setListError(data.error || "Couldn't delete the resident.");
      }
    } catch (err) {
      setListError(err instanceof NetworkError ? "Can't reach the server." : "Couldn't delete the resident.");
    }
    setDeletingId(null);
  };

  // Free the photo previews when leaving the screen
  useEffect(() => () => Object.values(shotsRef.current).forEach((s) => URL.revokeObjectURL(s.url)), []);

  // Webcam is on only while capturing — it switches off (light goes out) as soon as capture ends
  useEffect(() => {
    if (phase !== "capturing") return;
    let cancelled = false;
    setCamError(null);
    setCamReady(false);
    setFaceStatus("waiting");
    setAlignment(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setCamError("This browser can't use the camera. Try Chrome or Safari.");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        video.srcObject = stream;
        video.onloadedmetadata = () => {
          video.play();
          setVideoSize({ w: video.videoWidth, h: video.videoHeight });
          setCamReady(true);
        };
      })
      .catch((err) => !cancelled && setCamError(cameraErrorMessage(err)));

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      setCamReady(false);
    };
  }, [phase]);

  // Grab the current webcam frame as a JPEG for the angle being captured, then move on
  const takeShot = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const angle = targetRef.current;
    pauseUntilRef.current = Date.now() + PAUSE_AFTER_SHOT_MS; // stop a double capture

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        setShots((prev) => {
          if (prev[angle]) URL.revokeObjectURL(prev[angle].url);
          return { ...prev, [angle]: { blob, url: URL.createObjectURL(blob) } };
        });
        setSaveError((e) => (e && e.angle === angle ? null : e));

        const next = ANGLES[ANGLES.indexOf(angle) + 1];
        if (retakingRef.current || !next) {
          setPhase("review");
        } else {
          setTarget(next);
          setJustCaptured(true);
        }
      },
      "image/jpeg",
      0.92
    );
  }, []);

  // Detection loop: auto-capture once exactly one face holds steady
  useEffect(() => {
    if (phase !== "capturing" || !camReady || !modelsReady) return;
    let busy = false;
    let holdCount = 0;
    const id = setInterval(async () => {
      if (busy) return;
      if (Date.now() < pauseUntilRef.current) {
        holdCount = 0;
        setHold(0);
        return;
      }
      setJustCaptured(false);
      busy = true;
      try {
        const video = videoRef.current;
        if (!video || video.readyState < 2) return;
        const detections = await faceapi.detectAllFaces(
          video,
          new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 })
        );
        const status = detections.length === 0 ? "none" : detections.length === 1 ? "one" : "many";
        setFaceStatus(status);
        // Only count toward the photo while the face is lined up with the oval
        const align = status === "one"
          ? faceAlignment(detections[0].box, faceGuide(video.videoWidth, video.videoHeight))
          : null;
        setAlignment(align);
        holdCount = align === "ok" ? holdCount + 1 : 0;
        setHold(holdCount);
        if (holdCount >= HOLD_TICKS) {
          holdCount = 0;
          setHold(0);
          takeShot();
        }
      } finally {
        busy = false;
      }
    }, DETECT_INTERVAL_MS);
    return () => clearInterval(id);
  }, [phase, camReady, modelsReady, takeShot]);

  // Start the full five-photo sequence from the front
  const startCapture = () => {
    Object.values(shots).forEach((s) => URL.revokeObjectURL(s.url));
    setShots({});
    setSaveError(null);
    setRetaking(false);
    setTarget("front");
    pauseUntilRef.current = Date.now() + 1000; // a moment to get in position
    setPhase("capturing");
  };

  // Retake just one angle, then come back to review
  const retake = (angle) => {
    setRetaking(true);
    setTarget(angle);
    pauseUntilRef.current = Date.now() + 1000;
    setPhase("capturing");
  };

  // Send the name + five photos to the backend
  const handleSave = async () => {
    setPhase("saving");
    setSaveError(null);
    const body = new FormData();
    body.append("name", residentName.trim());
    ANGLES.forEach((angle) => body.append(angle, shots[angle].blob, `${angle}.jpg`));
    try {
      const res = await apiFetch("/residents", { method: "POST", body });
      const data = await res.json().catch(() => ({}));
      if (res.status === 201) {
        setSaved(data.resident);
        setPhase("done");
        loadResidents();
        return;
      }
      if (res.status === 401) return; // session expired — apiFetch already sent us to /login
      setSaveError({ message: data.error || "Couldn't register the resident. Try again.", angle: data.angle });
    } catch (err) {
      setSaveError({ message: err instanceof NetworkError ? "Can't reach the server." : "Something went wrong. Try again." });
    }
    setPhase("review");
  };

  // Clear everything for the next resident
  const reset = () => {
    Object.values(shots).forEach((s) => URL.revokeObjectURL(s.url));
    setShots({});
    setResidentName("");
    setSaved(null);
    setSaveError(null);
    setPhase("form");
  };

  const step = STEPS.find((s) => s.angle === target);
  const allCaptured = ANGLES.every((a) => shots[a]);

  // Status line under the webcam preview
  let statusText = "Starting camera…";
  if (camError) statusText = camError;
  else if (justCaptured) statusText = `Got it! Next: ${step.prompt.toLowerCase()}.`;
  else if (camReady && modelError) statusText = "Automatic capture isn't available. Use \"Take photo\" when ready.";
  else if (camReady && !modelsReady) statusText = "Loading face detection…";
  else if (faceStatus === "none") statusText = "No face found. Move closer and face the light.";
  else if (faceStatus === "many") statusText = "More than one face. Only the resident should be in view.";
  else if (faceStatus === "one" && alignment === "far") statusText = "Move closer so your face fills the oval.";
  else if (faceStatus === "one" && alignment === "close") statusText = "Move back a little.";
  else if (faceStatus === "one" && alignment === "off") statusText = "Line your face up inside the oval.";
  else if (faceStatus === "one") statusText = hold > 0 ? "Hold still…" : "Face lined up.";

  const guide = videoSize && faceGuide(videoSize.w, videoSize.h);
  const aligned = faceStatus === "one" && alignment === "ok";

  return (
    <div className="min-h-screen">

      {/* Header with back button */}
      <div className="bg-background border-b-2 border-border p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-window rounded cursor-pointer">
          <ArrowLeft className="w-6 h-6 text-bgtext" />
        </button>
        <h1 className="text-bgtext">Register Resident</h1>
      </div>

      <div className="p-4 space-y-4">

        {/* Done — confirmation (sequence diagram step 9a) */}
        {phase === "done" && saved && (
          <div className="bg-window border-2 border-border rounded-lg p-6 text-center space-y-4">
            <CheckCircle className="w-12 h-12 mx-auto text-statusgood" />
            <p className="text-lg text-bgtext">{saved.name} was registered as a resident.</p>
            <div className="flex gap-3">
              <button onClick={reset} className="flex-1 py-3 bg-panel text-wintext border-2 border-border rounded hover:bg-border cursor-pointer">
                Register Another
              </button>
              <button
                onClick={() => navigate("/dashboard")}
                className="flex-1 py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border cursor-pointer"
              >
                Back to Dashboard
              </button>
            </div>
          </div>
        )}

        {/* Resident name — shown before capture and during review */}
        {(phase === "form" || phase === "review" || phase === "saving") && (
          <div className="bg-window border-2 border-border rounded-lg p-4">
            <label htmlFor="residentName" className="block text-sm mb-2 text-bgtext">
              Resident Name
            </label>
            <input
              id="residentName"
              type="text"
              value={residentName}
              onChange={(e) => setResidentName(e.target.value)}
              maxLength={100}
              disabled={phase === "saving"}
              className="w-full px-4 py-2 border-2 border-border rounded bg-panel"
              placeholder="Enter resident name"
            />
          </div>
        )}

        {/* Before capture — explain what's about to happen */}
        {phase === "form" && (
          <div className="bg-window border-2 border-border rounded-lg p-4 space-y-3">
            <p className="text-sm text-bgtext">
              The webcam will take 5 photos of the resident: looking straight ahead, turned left,
              turned right, chin up and chin down. The resident lines their face up with
              the oval on screen; each photo is taken automatically after holding still for 3 seconds.
              Only the resident should be in view.
            </p>
            <button
              onClick={startCapture}
              disabled={!residentName.trim()}
              className="w-full py-3 border-2 border-border rounded hover:bg-border bg-panel text-wintext flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <Camera className="w-5 h-5" />
              Start Capture
            </button>
          </div>
        )}

        {/* Capturing — live webcam preview with the current prompt */}
        {phase === "capturing" && (
          <div className="bg-window border-2 border-border rounded-lg overflow-hidden">
            <div className="p-4 border-b-2 border-border">
              <p className="text-sm text-bgtextb">
                Photo {ANGLES.indexOf(target) + 1} of {ANGLES.length}: {step.label}
              </p>
              <p className="text-lg text-bgtext">{step.prompt}</p>
            </div>

            {/* Mirrored like a selfie camera so turning feels natural; the saved photo isn't mirrored */}
            <div className="relative aspect-video bg-black">
              <video ref={videoRef} playsInline muted className="w-full h-full object-cover -scale-x-100" />

              {/* Face guide: dims everything outside an oval the resident lines their face up with.
                  Drawn in the video's own coordinates; "slice" crops exactly like object-cover,
                  so the oval stays over the same part of the image on any screen size */}
              {guide && (
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none"
                  viewBox={`0 0 ${videoSize.w} ${videoSize.h}`}
                  preserveAspectRatio="xMidYMid slice"
                  aria-hidden="true"
                >
                  <defs>
                    <mask id="face-guide-mask">
                      <rect width={videoSize.w} height={videoSize.h} fill="white" />
                      <ellipse cx={guide.cx} cy={guide.cy} rx={guide.rx} ry={guide.ry} fill="black" />
                    </mask>
                  </defs>
                  <rect width={videoSize.w} height={videoSize.h} fill="black" fillOpacity="0.6" mask="url(#face-guide-mask)" />
                  <ellipse
                    cx={guide.cx}
                    cy={guide.cy}
                    rx={guide.rx}
                    ry={guide.ry}
                    fill="none"
                    stroke={aligned ? "var(--statusgood)" : "white"}
                    strokeWidth={videoSize.h * 0.008}
                    strokeDasharray={aligned ? undefined : `${videoSize.h * 0.03} ${videoSize.h * 0.02}`}
                  />

                  {/* Which way to turn for this photo */}
                  {TURN_ARROWS[target].map(({ side, rotate }) => {
                    const size = videoSize.h * 0.14;
                    const x = guide.cx + side * (guide.rx + size * 0.8);
                    return (
                      <g key={`${side}${rotate}`} transform={`translate(${x} ${guide.cy}) rotate(${rotate})`} className="animate-pulse">
                        <path d={arrowPath(size)} fill="white" fillOpacity="0.75" stroke="black" strokeOpacity="0.4" strokeWidth={size * 0.03} />
                      </g>
                    );
                  })}
                </svg>
              )}
              {hold > 0 && (
                <div className="absolute bottom-0 left-0 h-2 bg-statusgood" style={{ width: `${(hold / HOLD_TICKS) * 100}%` }} />
              )}
            </div>

            <div className="p-4 space-y-3">
              <p className={`text-sm ${camError || faceStatus === "many" ? "text-statusrisk" : "text-bgtext"}`}>{statusText}</p>
              <div className="flex gap-3">
                <button
                  onClick={() => setPhase(retaking || allCaptured ? "review" : "form")}
                  className="flex-1 py-3 bg-panel text-wintext border-2 border-border rounded hover:bg-border cursor-pointer"
                >
                  Cancel
                </button>
                {/* Manual fallback, e.g. if the face detector couldn't download */}
                <button
                  onClick={takeShot}
                  disabled={!camReady}
                  className="flex-1 py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border cursor-pointer disabled:opacity-50"
                >
                  Take Photo
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Error from the backend (sequence diagram step 7b) */}
        {saveError && (phase === "review" || phase === "saving") && (
          <div role="alert" className="bg-window border-2 border-statusrisk rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-statusrisk mt-0.5 shrink-0" />
            <p className="text-bgtext">{saveError.message}</p>
          </div>
        )}

        {/* Photos taken so far — retake any one of them */}
        {(phase === "capturing" || phase === "review" || phase === "saving") && Object.keys(shots).length > 0 && (
          <div className="bg-window border-2 border-border rounded-lg p-4">
            <p className="block text-sm mb-3 text-bgtext">Photos</p>
            <div className="grid grid-cols-5 gap-2">
              {STEPS.map(({ angle, label }) => (
                <div key={angle} className="text-center">
                  <div
                    className={`aspect-square bg-panel rounded overflow-hidden border-2 ${
                      saveError?.angle === angle ? "border-statusrisk" : "border-border"
                    }`}
                  >
                    {shots[angle] && <img src={shots[angle].url} alt={`${label} photo`} className="w-full h-full object-cover" />}
                  </div>
                  <p className="text-xs mt-1 text-bgtextb">{label}</p>
                  {phase === "review" && shots[angle] && (
                    <button onClick={() => retake(angle)} className="text-xs text-bgtext underline cursor-pointer flex items-center gap-1 mx-auto">
                      <RefreshCw className="w-3 h-3" />
                      Retake
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Review — save, or start the whole capture again */}
        {(phase === "review" || phase === "saving") && (
          <div className="flex gap-3">
            <button
              onClick={startCapture}
              disabled={phase === "saving"}
              className="flex-1 py-3 bg-panel text-wintext border-2 border-border rounded hover:bg-border cursor-pointer disabled:opacity-50"
            >
              Start Over
            </button>
            <button
              onClick={handleSave}
              disabled={phase === "saving" || !allCaptured || !residentName.trim()}
              className="flex-1 py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border cursor-pointer disabled:opacity-50 disabled:cursor-wait"
            >
              {phase === "saving" ? "Saving…" : "Save Resident"}
            </button>
          </div>
        )}

        {/* Registered residents — hidden while capturing so the webcam has the screen */}
        {(phase === "form" || phase === "done") && (
          <div className="bg-window border-2 border-border rounded-lg p-4">
            <h2 className="text-bgtext mb-3">Registered Residents</h2>
            {listError && <p role="alert" className="text-sm text-statusrisk mb-2">{listError}</p>}
            {residents === null && !listError && <p className="text-sm text-bgtextb">Loading…</p>}
            {residents?.length === 0 && <p className="text-sm text-bgtextb">No residents registered yet.</p>}
            {residents?.length > 0 && (
              <ul className="divide-y divide-border">
                {residents.map((r) => (
                  <li key={r.id} className="py-2 flex items-center gap-3">
                    <div className="flex-1">
                      <p className="text-bgtext">{r.name}</p>
                      <p className="text-xs text-bgtextb">Registered by {r.registered_by} · #{r.id}</p>
                    </div>
                    {r.can_delete && (
                      <button
                        onClick={() => handleDelete(r)}
                        disabled={deletingId === r.id}
                        className="flex items-center gap-1 text-sm bg-panel text-statusrisk border-2 border-statusrisk rounded px-3 py-1 hover:bg-border cursor-pointer disabled:opacity-50"
                      >
                        <Trash2 className="w-4 h-4" />
                        {deletingId === r.id ? "Deleting…" : "Delete"}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
