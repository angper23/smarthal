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
    <div className="min-h-screen bg-gray-50">

      {/* Header with back button */}
      <div className="bg-white border-b-2 border-gray-300 p-4 flex items-center gap-3">
        <button onClick={() => navigate("/dashboard")} className="p-1 hover:bg-gray-100 rounded">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-2xl">Register Resident</h1>
      </div>

      <div className="p-4">
        <form onSubmit={handleSave} className="space-y-4">

          {/* Resident name input */}
          <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
            <label htmlFor="residentName" className="block text-sm mb-2 text-gray-700">
              Resident Name
            </label>
            <input
              id="residentName"
              type="text"
              value={residentName}
              onChange={(e) => setResidentName(e.target.value)}
              className="w-full px-4 py-2 border-2 border-gray-300 rounded bg-white"
              placeholder="Enter resident name"
            />
          </div>

          {/* Face image upload section */}
          <div className="bg-white border-2 border-gray-300 rounded-lg p-4">
            <label className="block text-sm mb-3 text-gray-700">Face Image</label>

            {/* Image preview area — shows upload icon before upload, camera icon after */}
            <div className="mb-4 aspect-square bg-gray-200 border-2 border-dashed border-gray-400 rounded-lg flex items-center justify-center">
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
                className="w-full py-3 border-2 border-gray-300 rounded hover:bg-gray-100 flex items-center justify-center gap-2"
              >
                <Upload className="w-5 h-5" />
                Upload from Gallery
              </button>

              <button
                type="button"
                onClick={handleFileUpload}
                className="w-full py-3 border-2 border-gray-300 rounded hover:bg-gray-100 flex items-center justify-center gap-2"
              >
                <Camera className="w-5 h-5" />
                Capture Photo
              </button>
            </div>
          </div>

          {/* Submit button — triggers handleSave */}
          <button
            type="submit"
            className="w-full py-3 bg-gray-800 text-white rounded border-2 border-gray-800 hover:bg-gray-700"
          >
            Save Resident
          </button>
        </form>
      </div>
    </div>
  );
}
