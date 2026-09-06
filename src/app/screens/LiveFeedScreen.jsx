// Live Feed screen — the main feature of SmartHal
// Uses the device webcam and face-api.js to detect faces in real time
// Draws green bounding boxes on a canvas overlay on top of the video feed
import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router";
import Webcam from "react-webcam";
import * as faceapi from "face-api.js";
import { ArrowLeft, Circle, AlertTriangle, RefreshCw } from "lucide-react";

// URL where the face detection AI model weights are downloaded from
const MODEL_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model";

// How often to scan for faces — 200ms means 5 times per second
const DETECTION_INTERVAL_MS = 200;

export function LiveFeedScreen() {
  const navigate = useNavigate();

  // Ref to the webcam component — used to grab video frames
  const webcamRef = useRef(null);

  // Ref to the canvas element — used to draw bounding boxes on top of the video
  const canvasRef = useRef(null);

  // Ref to store the detection interval so we can clear it on unmount
  const intervalRef = useRef(null);

  // Whether the AI model has finished downloading and is ready to use
  const [modelsLoaded, setModelsLoaded] = useState(false);

  // Whether the model failed to download (e.g. no internet)
  const [modelError, setModelError] = useState(false);

  // Whether the user denied camera access in the browser
  const [webcamError, setWebcamError] = useState(false);

  // Whether a face is currently detected in the frame
  const [faceDetected, setFaceDetected] = useState(false);

  // How many faces are currently detected
  const [faceCount, setFaceCount] = useState(0);

  // On mount — download the face detection model from CDN
  useEffect(() => {
    faceapi.nets.tinyFaceDetector
      .loadFromUri(MODEL_URL)
      .then(() => setModelsLoaded(true))  // Model ready — detection can begin
      .catch(() => setModelError(true));   // Load failed — show error message

    // Cleanup: stop detection when the user leaves this screen
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Detection loop — runs every 200ms once models are loaded
  const startDetection = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(async () => {
      const video = webcamRef.current?.video;
      const canvas = canvasRef.current;

      // Skip this tick if the video isn't ready yet
      if (!video || video.readyState !== 4 || !canvas) return;

      // Run face detection on the current video frame
      const detections = await faceapi.detectAllFaces(
        video,
        new faceapi.TinyFaceDetectorOptions({
          inputSize: 320,       // Smaller = faster, less accurate
          scoreThreshold: 0.5,  // Confidence required to count as a face
        })
      );

      // Match canvas size to the actual video dimensions
      const dims = { width: video.videoWidth, height: video.videoHeight };
      canvas.width = dims.width;
      canvas.height = dims.height;

      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear previous boxes

      // Scale detection coordinates to match the canvas size
      const resized = faceapi.resizeResults(detections, dims);

      // Draw a green rectangle around each detected face
      resized.forEach(({ box }) => {
        ctx.strokeStyle = "#16a34a"; // Green
        ctx.lineWidth = 3;
        ctx.strokeRect(box.x, box.y, box.width, box.height);
      });

      // Update state to drive the status badge in the UI
      setFaceCount(detections.length);
      setFaceDetected(detections.length > 0);
    }, DETECTION_INTERVAL_MS);
  }, []);

  // Start the detection loop as soon as the model is ready
  useEffect(() => {
    if (modelsLoaded) startDetection();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [modelsLoaded, startDetection]);

  // Retry downloading the model if it previously failed
  const handleRetryModels = () => {
    setModelError(false);
    faceapi.nets.tinyFaceDetector
      .loadFromUri(MODEL_URL)
      .then(() => setModelsLoaded(true))
      .catch(() => setModelError(true));
  };

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
            <Circle className="w-3 h-3 fill-green-600 text-green-600" />
            <span className="text-sm">Camera Online</span>
          </div>
          <div className="text-sm">
            {/* Show loading state while model downloads */}
            {!modelsLoaded && !modelError && (
              <span className="text-gray-500">Loading detection models…</span>
            )}
            {/* Show error if model failed to load */}
            {modelError && (
              <span className="text-red-600">Model load failed</span>
            )}
            {/* Show live detection result once model is ready */}
            {modelsLoaded && (
              <span className={faceDetected ? "text-orange-600 font-medium" : "text-green-600"}>
                {faceDetected ? `Person Detected (${faceCount})` : "No Face Detected"}
              </span>
            )}
          </div>
        </div>

        {/* Error message shown if the user blocks camera access */}
        {webcamError && (
          <div className="bg-orange-50 border-2 border-orange-300 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-orange-800">Camera access denied</p>
              <p className="text-sm text-orange-700 mt-1">
                Allow camera access in your browser settings and reload the page.
              </p>
            </div>
          </div>
        )}

        {/* Error message shown if the AI model fails to download */}
        {modelError && (
          <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-red-800">Failed to load detection models</p>
              <p className="text-sm text-red-700 mt-1">Check your internet connection and try again.</p>
            </div>
            <button
              onClick={handleRetryModels}
              className="flex items-center gap-1 text-sm text-red-700 border border-red-300 rounded px-2 py-1 hover:bg-red-100"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          </div>
        )}

        {/* Webcam + canvas overlay — only shown if camera access was granted */}
        {!webcamError && (
          <div className="bg-white border-2 border-gray-300 rounded-lg overflow-hidden">
            <div className="relative aspect-video bg-black">

              {/* The webcam video stream */}
              <Webcam
                ref={webcamRef}
                audio={false}
                className="w-full h-full object-cover"
                videoConstraints={{ facingMode: "user" }} // Use the front-facing camera
                onUserMediaError={() => setWebcamError(true)} // Fires if camera is blocked
                mirrored // Mirror so the user sees themselves correctly
              />

              {/* Canvas sits on top of the video — bounding boxes are drawn here
                  scaleX(-1) mirrors the canvas to match the mirrored webcam */}
              <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full"
                style={{ transform: "scaleX(-1)" }}
              />
            </div>

            {/* Footer showing camera info and detection badge */}
            <div className="p-4 border-t-2 border-gray-300 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Resolution: 1080p</p>
                <p className="text-sm text-gray-600">Location: Main Entrance</p>
              </div>
              {/* Detection status badge — changes colour based on result */}
              <div
                className={`px-3 py-1 rounded-full text-sm font-medium border-2 ${
                  faceDetected
                    ? "bg-orange-50 text-orange-700 border-orange-300"
                    : "bg-green-50 text-green-700 border-green-300"
                }`}
              >
                {faceDetected ? `Person Detected (${faceCount})` : "No Face Detected"}
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
