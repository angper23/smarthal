// Register Resident screen — allows adding a new known person to the system
// This is a mock UI — no data is actually saved, the form just shows a success alert
import { useState } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, Upload, Camera } from "lucide-react";

export function RegisterResidentScreen() {
  const navigate = useNavigate();

  // Track the resident's name as the user types
  const [residentName, setResidentName] = useState("");

  // Track whether the user has "uploaded" a photo (mock — no real file handling)
  const [imageUploaded, setImageUploaded] = useState(false);

  // Mock save — shows an alert and returns to the dashboard
  const handleSave = (e) => {
    e.preventDefault(); // Stop page from refreshing on form submit
    alert("Resident registered successfully!");
    navigate("/dashboard");
  };

  // Mock file upload — just flips the imageUploaded flag to show the preview state
  const handleFileUpload = () => {
    setImageUploaded(true);
  };

  return (
    <div className="min-h-screen">

      {/* Header with back button */}
      <div className="bg-background border-b-2 border-border p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-window rounded cursor-pointer">
          <ArrowLeft className="w-6 h-6 text-bgtext" />
        </button>
        <h1 className="text-bgtext">Register Resident</h1>
      </div>

      <div className="p-4">
        <form onSubmit={handleSave} className="space-y-4">

          {/* Resident name input */}
          <div className="bg-window border-2 border-border rounded-lg p-4">
            <label htmlFor="residentName" className="block text-sm mb-2 text-bgtext">
              Resident Name
            </label>
            <input
              id="residentName"
              type="text"
              value={residentName}
              onChange={(e) => setResidentName(e.target.value)}
              className="w-full px-4 py-2 border-2 border-border rounded bg-panel"
              placeholder="Enter resident name"
            />
          </div>

          {/* Face image upload section */}
          <div className="bg-window border-2 border-border rounded-lg p-4">
            <label className="block text-sm mb-3 text-bgtext">Face Image</label>

            {/* Image preview area — shows upload icon before upload, camera icon after */}
            <div className="mb-4 aspect-square bg-panel border-2 border-dashed border-border rounded-lg flex items-center justify-center">
              {imageUploaded ? (
                // Shown after the user clicks upload
                <div className="text-center">
                  <Camera className="w-12 h-12 mx-auto mb-2 text-gray-600" />
                  <p className="text-sm text-gray-600">Image uploaded</p>
                </div>
              ) : (
                // Shown before any image is selected
                <div className="text-center">
                  <Upload className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                  <p className="text-sm text-gray-500">No image uploaded</p>
                </div>
              )}
            </div>

            {/* Upload and capture buttons — both trigger the mock upload handler */}
            <div className="space-y-2">
              <button
                type="button"
                onClick={handleFileUpload}
                className="w-full py-3 border-2 border-border rounded hover:bg-border bg-panel flex items-center justify-center gap-2 cursor-pointer"
              >
                <Upload className="w-5 h-5" />
                Upload from Gallery
              </button>

              <button
                type="button"
                onClick={handleFileUpload}
                className="w-full py-3 border-2 border-border rounded hover:bg-border bg-panel flex items-center justify-center gap-2 cursor-pointer"
              >
                <Camera className="w-5 h-5" />
                Capture Photo
              </button>
            </div>
          </div>

          {/* Submit button — triggers handleSave */}
          <button
            type="submit"
            className="w-full py-3 bg-panel text-wintext rounded border-2 border-border hover:bg-border cursor-pointer"
          >
            Save Resident
          </button>
        </form>
      </div>
    </div>
  );
}
