# SmartHal

A home security monitoring prototype (CPSC 355 capstone). A camera watches the door, and the app shows the live video behind a real login, with every face labeled: a registered resident's name in green, or "Unknown" in orange. Residents are registered with the webcam (five face angles each).

**Contents**
1. [Install on Mac](#1-install-on-mac)
2. [Install on Windows](#2-install-on-windows)
3. [Start the app (every time)](#3-start-the-app-every-time)
4. [Using the app](#4-using-the-app)
5. [Troubleshooting](#5-troubleshooting)
6. [For developers](#6-for-developers)

**How it fits together:** SmartHal is two programs that run at the same time, each in its own terminal window:

| Program | Folder | What it does | Address |
|---|---|---|---|
| **Backend** | `smarthal-backend/` | Logins, the database, the camera stream | `http://localhost:5001` |
| **Frontend** | `smarthal-frontend/` | The website you use | `http://localhost:5173` |

You set both up once (sections 1 or 2), then start both whenever you want to use the app (section 3).

---

## 1. Install on Mac

**Step 1: Install the tools** (skip any you already have):
- **Node.js:** download the **LTS** version from [nodejs.org](https://nodejs.org) and run the installer.
- **Python 3.9 or newer:** most Macs already have it. Check by opening **Terminal** and typing `python3 --version`. If it's missing, install it from [python.org](https://www.python.org/downloads/).
- **Git:** type `git --version` in Terminal. If it asks to install developer tools, click **Install**.

**Step 2: Download the code.** In Terminal:
```bash
git clone https://github.com/angper23/smarthal.git
cd smarthal
```

**Step 3: Set up the backend.** Still in Terminal, from the `smarthal` folder:
```bash
cd smarthal-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python faces.py
cp .env.example .env
python seed_user.py
```
- After `source venv/bin/activate`, your prompt starts with `(venv)`. That's normal: it means the project's Python packages are active.
- `pip install` takes **a few minutes** the first time: the face library for Register Resident is large.
- `python faces.py` downloads the **face models** (about 280 MB) into `smarthal-backend/models/` and checks they load. It should end with `models ready`. Run it once; it's skipped automatically next time.
- `seed_user.py` creates **your login** (there's no sign-up page). Pick a username and a password of at least 8 characters. **Nothing appears while you type the password; that's normal.** Type it again to confirm, then type `admin` for the role.
- `.env` holds the camera's address and password. Leave it as it is unless you have the real camera details (ask Angel). Without them, everything works except the live video.

**Step 4: Set up the frontend.** Open a **second** Terminal window (Cmd + N), go to the `smarthal` folder, and run:
```bash
cd smarthal-frontend
npm install
cp .env.example .env.development
```

✅ Setup is done. Go to [section 3](#3-start-the-app-every-time) to start the app.

---

## 2. Install on Windows

> **Which terminal?** Use **Command Prompt** (search "cmd" in the Start menu) or **PowerShell**. VS Code's built-in terminal is PowerShell, which also works. **Don't use Git Bash:** the password prompt doesn't work there.

**Step 1: Install the tools** (skip any you already have):
- **Node.js:** download the **LTS** version from [nodejs.org](https://nodejs.org) and run the installer.
- **Python 3.9 or newer:** download it from [python.org](https://www.python.org/downloads/). ⚠️ On the installer's **first screen, tick "Add python.exe to PATH"** before clicking Install.
- **Git:** download it from [git-scm.com](https://git-scm.com) and install with the default options.

After installing, **close and reopen** your terminal so it picks up the new tools.

**Step 2: Download the code.**
```bat
git clone https://github.com/angper23/smarthal.git
cd smarthal
```

**Step 3: Set up the backend.** From the `smarthal` folder:
```bat
cd smarthal-backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python faces.py
copy .env.example .env
python seed_user.py
```
- If `py` isn't recognized, use `python -m venv venv` instead.
- **PowerShell only:** if activating says *"running scripts is disabled on this system"*, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, then run `venv\Scripts\activate` again.
- After activating, your prompt starts with `(venv)`. That's normal.
- `pip install` takes **a few minutes** the first time: the face library for Register Resident is large.
- `python faces.py` downloads the **face models** (about 280 MB) into `smarthal-backend/models/` and checks they load. It should end with `models ready`. Run it once; it's skipped automatically next time.
- `seed_user.py` creates **your login** (there's no sign-up page). Pick a username and a password of at least 8 characters. **Nothing appears while you type the password; that's normal.** Type it again to confirm, then type `admin` for the role.
- `.env` holds the camera's address and password. Leave it as it is unless you have the real camera details (ask Angel). Without them, everything works except the live video.

**Step 4: Set up the frontend.** Open a **second** terminal window, go to the `smarthal` folder, and run:
```bat
cd smarthal-frontend
npm install
copy .env.example .env.development
```

✅ Setup is done. Go to [section 3](#3-start-the-app-every-time) to start the app.

---

## 3. Start the app (every time)

You need **two terminal windows open at the same time**. Start in the `smarthal` folder in each.

**Window 1: the backend**

| Mac | Windows |
|---|---|
| `cd smarthal-backend` | `cd smarthal-backend` |
| `source venv/bin/activate` | `venv\Scripts\activate` |
| `python app.py` | `python app.py` |

Wait for `Running on http://127.0.0.1:5001`.

**Window 2: the frontend**

| Mac and Windows |
|---|
| `cd smarthal-frontend` |
| `npm run dev` |

Wait for `http://localhost:5173`.

**Then open http://localhost:5173 in your browser** and log in with the account you made in setup.

**To stop:** click into each window and press **Ctrl + C**. (On Mac, don't press Ctrl + Z; that pauses the program instead of stopping it.)

**After downloading new changes** with `git pull`: run `pip install -r requirements.txt` in `smarthal-backend` (with `(venv)` active) and `npm install` in `smarthal-frontend`, in case new packages were added. Then start the app as usual.

---

## 4. Using the app

**Logging in:** use the username and password you created with `seed_user.py`. Wrong details show "Invalid username or password". After 5 wrong tries within 15 minutes, that username is blocked for a while (at most 15 minutes).

**The screens:**

| Screen | What it does | Real or mock? |
|---|---|---|
| **Login** | Checks your username and password | ✅ Real |
| **Dashboard** | The home page, with buttons for every feature, **Change Password** and **Logout** | ✅ Real buttons; the status and alert cards show sample data |
| **Live Feed** | The live camera video. Every face gets a box: **green with the name** for a registered resident, **orange "Unknown"** for anyone else | ✅ Real (needs the camera; see below) |
| **Change Password** | Asks for your current password, then a new one (8+ characters). Signs out any other device logged in to your account | ✅ Real |
| **Event History / Event Detail** | A list of past detections | 🟡 Sample data |
| **Register Resident** | Registers a known person with the **webcam**: five photos (front, left, right, chin up, chin down), each taken automatically once their face is lined up in the on-screen oval for 3 seconds. Also lists registered residents, with **Delete** | ✅ Real (needs a webcam) |
| **Alert Settings** | Notification switches | 🟡 Mock; resets on refresh |

**Good to know:**
- **Staying logged in:** your login lasts until you log out, close the tab, or are inactive for 30 minutes. Restarting the backend also logs everyone out.
- **More accounts:** run `python seed_user.py` again in `smarthal-backend` (with `(venv)` active).
- **Forgot a password?** Run `python reset_password.py` in `smarthal-backend` (with `(venv)` active). It asks for the username and a new password.
- **The live camera only works on the laptop it's plugged into** (Angel's), through Mac Internet Sharing. On any other computer, Live Feed says "Camera unreachable", which is expected.
- **Registering a resident:** the browser asks for **camera permission** the first time; click Allow. Only the resident should be in view. If a photo is rejected (no face, two faces, or a different person than the front photo), that photo is outlined in red; click **Retake** under it. Registered residents' photos stay on your computer (`smarthal-backend/data/residents/`) and are never uploaded to GitHub.
- **Deleting a resident:** only the person who registered them, or an admin, sees the **Delete** button.
- **Recognition on Live Feed:** names appear within about a second of someone stepping into view, and update about 3 times a second. When it isn't sure, it says **Unknown**: calling a stranger a resident would be the worse mistake. Only registered residents get names, and newly registered or deleted residents take effect right away. Frames are analyzed in memory only; nothing from the camera is saved.

---

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| **Windows:** `'cp' is not recognized…` or `'source' is not recognized…` | Those are Mac commands. Use the Windows ones: `copy` instead of `cp`, `venv\Scripts\activate` instead of `source venv/bin/activate`. |
| **Windows:** `'py' is not recognized…` | Use `python -m venv venv` instead. If `python` opens the Microsoft Store or isn't found either, reinstall Python from python.org with **"Add python.exe to PATH"** ticked, then reopen the terminal. |
| **Windows PowerShell:** *"running scripts is disabled on this system"* | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, then activate again. Or use Command Prompt instead. |
| **Mac:** `python3: command not found` | Install Python from python.org, then open a new Terminal window. |
| `No module named flask` (or `dotenv`, `cv2`, `bcrypt`) | The `venv` isn't active. Activate it (your prompt should start with `(venv)`), then run `python app.py` again. |
| `npm: command not found` / `'npm' is not recognized` | Install Node.js (LTS) from nodejs.org, then reopen the terminal. |
| Login page says **"Can't reach the server"** | The backend window isn't running, or it stopped with an error. Check Window 1. |
| **"Invalid username or password"** with the right details | Usernames are case-sensitive. If you forgot the password, run `python reset_password.py` in `smarthal-backend`. |
| **"Too many attempts"** | 5 wrong passwords within 15 minutes. Wait (at most 15 minutes), or restart the backend to clear it. |
| **"Address already in use"** / **"Port 5001 is in use"** | The backend is already running in another window. Use that one, or stop it with Ctrl + C first. |
| **Live Feed says "Camera unreachable"** | Expected unless you're on the laptop the camera is plugged into. On that laptop: plug in the camera's Ethernet adapter and turn on **System Settings → General → Sharing → Internet Sharing**. It reconnects within a few seconds. |
| `python faces.py` fails, or Register Resident says **"Couldn't register the resident"** right away | The face models didn't download. Check your internet connection and run `python faces.py` again (with `(venv)` active). |
| Register Resident: **"Camera access was blocked"** | Allow the camera for `localhost:5173` in your browser (the camera icon in the address bar), then click Start Capture again. On Mac, also check **System Settings → Privacy & Security → Camera** for your browser. |
| Register Resident: the oval never turns green | Move closer so your face fills the oval, face a light, and make sure only one person is in view. You can also press **Take Photo** to take it manually. |
| Live Feed says **"Face recognition isn't working"** | The face models are missing. In `smarthal-backend` with `(venv)` active, run `python faces.py`, then restart the backend. |
| A registered resident shows as **Unknown** on Live Feed | The security camera sees faces from higher up than the webcam did, so matches score lower. Face the camera and come closer; if it keeps happening, lower the threshold a little (`RECOGNITION_THRESHOLD=0.35` in `smarthal-backend/.env`, then restart the backend). Don't go much lower, or strangers could be mistaken for residents. |

---

## 6. For developers

### Project layout
```
smarthal/
├── README.md                 ← this file
├── smarthal-frontend/        ← React + Vite app
│   ├── src/app/              ← screens, routes, login state, API helper
│   ├── src/styles/           ← Tailwind setup and theme colors
│   ├── package.json
│   └── .env.example          ← copy to .env.development
└── smarthal-backend/         ← Flask server
    ├── app.py                ← the server and every endpoint
    ├── auth.py               ← password hashing, sessions, rate limiting
    ├── camera.py             ← reads the camera's RTSP stream on a background thread
    ├── faces.py              ← face detection + face embeddings (InsightFace or OpenCV)
    ├── recognition.py        ← names faces on the live camera against registered residents
    ├── db.py, schema.sql     ← SQLite database and its tables
    ├── seed_user.py          ← create an account
    ├── reset_password.py     ← reset a forgotten password
    ├── tests/                ← pytest tests
    ├── .env.example          ← copy to .env
    ├── models/               ← face models, downloaded by faces.py (gitignored)
    └── data/                 ← database + residents' photos (gitignored)
```
Every file starts with a short summary, and every function has a one-to-three-line explanation. Good places to start: `smarthal-frontend/src/app/routes.js` and `smarthal-backend/app.py`.

### How it works
```
Reolink camera → (RTSP) → Flask backend ─┬→ (MJPEG over HTTP) → browser <img>
                                         └→ recognition.py → GET /recognitions → boxes + names drawn over the <img>
```
- **Video:** browsers can't play RTSP, so the backend reads the camera stream (`camera.py`) and re-serves it as MJPEG ("one JPEG after another"), which a plain `<img>` can show. It's capped at 10 frames per second.
- **Recognition** runs on the backend (`recognition.py`). While someone has Live Feed open, a background thread takes the newest camera frame about 3 times a second (shrunk to 1280 px; ~0.15 s per pass on an M2), finds the faces with InsightFace, and compares each one against **every saved angle of every resident**. Each resident's score is their best-matching angle; the best resident at or above the threshold (0.4 for InsightFace) gives the name, otherwise "Unknown". Live Feed polls `GET /recognitions` and draws the boxes on a canvas over the video. The thread stops when nobody has asked for 10 seconds, and frames are never saved.
- **Login:** passwords are bcrypt-hashed in SQLite (`users` table). A login returns a random token, kept in the browser's `sessionStorage` and sent as `Authorization: Bearer <token>`. Sessions live in the backend's memory and expire after 30 minutes without activity. Every screen except `/login` is behind a route guard (`RequireAuth` in `AuthContext.jsx`).
- **The video needs a login too:** an `<img>` can't send headers, so Live Feed first gets a short-lived **stream token** (60 seconds) and puts it in the video URL. An open stream re-checks the session every 5 seconds and stops when you log out.
- **Register Resident:** the browser's webcam takes one photo per angle; `face-api.js` checks there's exactly one face, lined up with the guide oval, before each photo. The backend (`POST /residents`) checks every photo again with **InsightFace** (`faces.py`): exactly one face per photo, and every angle must look like the same person as the front photo. It stores one face **embedding** per angle in `resident_face_angles`, plus the photos (re-encoded, no metadata) in `data/residents/<id>/`. Recognition on the live feed will compare faces against every saved angle and keep the best match, so a resident seen from the side still matches.
- **Camera disconnects:** `is_online()` checks how long ago the last frame arrived (5 s), because a dead RTSP connection can make `read()` hang. The open/read timeouts are passed to `cv2.VideoCapture(...)` when it's created; setting them afterward is silently ignored.

### Backend endpoints
Authenticated endpoints need `Authorization: Bearer <token>`. A missing or expired token gets `401 {"error": "Authentication required"}`.

| Endpoint | Auth | What it does |
|---|---|---|
| `POST /login` | none | Body `{"username", "password"}`. `200 {"token", "expires_in": 1800, "user": {"id", "username", "role"}}`. Wrong password or unknown user: `401 {"error": "Invalid username or password"}` (same message and timing either way). 5 failures per username + IP in 15 min: `429` with `Retry-After`. |
| `POST /logout` | bearer | Ends the session (`204`); its open video stream stops within ~5 s. |
| `GET /me` | bearer | `{"user": {"id", "username", "role"}}` |
| `POST /change-password` | bearer | Body `{"current_password", "new_password"}`. `204`, and every **other** session of the account is signed out. `403` wrong current password (5 tries per 15 min, then `429`); `400` if the new one is under 8 characters, over 72 bytes, or unchanged. |
| `POST /stream-token` | bearer | `{"stream_token", "expires_in": 60}` for opening `/video_feed`. |
| `GET /video_feed?stream_token=…` | stream token | The MJPEG camera stream. Fetch a new token for each reconnect. |
| `GET /status` | bearer | `{"camera_online": true\|false}` |
| `GET /recognitions` | bearer | Who's in view: `{"faces": [{"box": [x, y, w, h], "resident_id", "name", "score"}], "age_seconds", "threshold", "error", "camera_online"}`. `box` is fractions of the frame; `name` is `null` for Unknown. Polling it is what keeps recognition running. |
| `POST /residents` | bearer | **Multipart** form: `name` (1–100 characters) plus five image files `front`, `left`, `right`, `up`, `down` (each under 5 MB). Each must contain exactly one face, and each angle must match the `front` photo. `201 {"resident": {"id", "name", "angles"}}`. A bad photo gives `400 {"error", "angle", "reason"}` (`missing`, `too_large`, `invalid_image`, `no_face`, `multiple_faces`, `different_person`) so the screen can ask for a retake of just that angle. |
| `GET /residents` | bearer | `{"residents": [{"id", "name", "registered_by", "angles", "can_delete"}]}`, newest first. |
| `DELETE /residents/<id>` | bearer | Deletes the resident, their embeddings and photos. Only the user who registered them, or an admin (`403` otherwise). `204`; `404` not found; `409` if recorded detection events refer to them. |

### Configuration
**Backend, `smarthal-backend/.env`** (gitignored; never commit it):

| Variable | Default | Purpose |
|---|---|---|
| `RTSP_URL` | (required) | The camera's full RTSP URL, password included. Kept only here, never in the database. |
| `DB_PATH` | `data/dev.db` | SQLite file, relative to `smarthal-backend/`. `*.db` and `data/` are gitignored. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated frontend origins allowed to call the API. `*` is refused on purpose. |
| `FACE_BACKEND` | `insightface` | Face library for Register Resident: `insightface` (most accurate in our tests; pinned to 1.0.1, the tested version) or `opencv` (YuNet + SFace; ~7x faster, lighter). InsightFace's pretrained models are licensed for non-commercial use only. |
| `FACE_MODELS_DIR` | `models` | Where `faces.py` downloads the face models. Gitignored. |
| `RECOGNITION_THRESHOLD` | `0.4` (InsightFace), `0.363` (OpenCV) | How similar a camera face must be to a resident's saved angle to be named. Higher = fewer false matches but more residents shown as Unknown. |
| `RESIDENT_PHOTOS_DIR` | `data/residents` | Where residents' photos are saved. Gitignored (photos of real people). |

**Frontend, `smarthal-frontend/.env.development`** (gitignored): `VITE_BACKEND_URL` (default `http://localhost:5001`).

### Tests
With `(venv)` active, in `smarthal-backend`:
```
pip install -r requirements-dev.txt
python -m pytest tests
```
They use a fake camera and a temporary database, so they need neither the camera nor your real data.

### Things not to break
- **Keep `crossOrigin` before `src` on the Live Feed `<img>`.** Recognition runs on the backend now, so the browser doesn't read the video's pixels, but if `src` is set first, Safari opens the stream twice. (Register Resident still runs `face-api.js` in the browser, on the webcam.)
- **When unsure, say Unknown.** Don't lower `RECOGNITION_THRESHOLD` to make matches "work": a stranger labeled as a resident is the failure a security camera must avoid.
- **Port 5001, not Flask's default 5000:** on Mac, AirPlay Receiver uses port 5000.
- **The backend binds to `127.0.0.1` only** and CORS allows only the frontend's origin. Don't change these to `0.0.0.0` or `*`.
- **Never commit** `.env`, `.env.development`, `*.db`, `data/`, `models/` or any password. The repo is public, and `data/residents/` holds photos of real people.
- **Embeddings from different face libraries can't be compared.** Each saved angle records its `model`; if you switch `FACE_BACKEND`, residents registered with the other library need registering again.
