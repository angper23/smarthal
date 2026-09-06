# SmartHal

A home security monitoring prototype. The idea: a camera watches your front door, detects when someone's there, and logs/alerts on it. Residents can be registered so the system can (eventually) tell them apart from strangers.

**Status:** this is a front-end-only prototype — there's no server and no database. Most screens just display fake, hardcoded data so the app *looks* finished for demo purposes. The one piece of real functionality is live face **detection** (noticing a face is there) on the Live Feed screen — there's no face **recognition** yet (knowing *whose* face it is).

## Run it

```bash
npm install
npm run dev
```

This installs the dependencies and starts a local dev server. Open the URL it prints in your terminal (usually `http://localhost:5173`) in your browser.

## How the app is put together

It's a normal React app: each "screen" (page) is its own component file, and `routes.js` maps a URL to the screen that should render there. Clicking a button in the app just calls `navigate("/some-path")`, which swaps out the screen — there's no page reload, it all happens in the browser.

The flow a user follows: **Login → Dashboard → (Live Feed / Event History / Register Resident / Alert Settings)**. Every screen other than the dashboard has a back button that returns you the way you came.

## What's real vs. what's mocked

- **Real:** the Live Feed screen turns on your actual webcam and runs an AI model (`face-api.js`) in the browser to detect faces in the video, drawing a box around each one it finds, live.
- **Mocked — looks functional but isn't wired to anything real:**
  - **Login** — typing anything and hitting submit logs you in. There's no password check, no account system.
  - **Event History / Event Detail** — the list of past "detections" is a fixed array written directly in the code, not data from a camera or database.
  - **Register Resident** — the form lets you type a name and "upload" a photo, but nothing is stored; hitting Save just pops an alert box and returns to the dashboard.
  - **Alert Settings** — the toggles work visually (they flip on/off), but the value only lives in that screen's memory. Refresh the page and it's back to default.

## File-by-file guide

### Root config files
These aren't app code — they configure the tools that build and run the app.
- `index.html` — the one HTML page the whole app lives inside. React finds the empty `<div id="root">` in here and injects the entire UI into it.
- `package.json` — lists every dependency the project needs (React, Tailwind, face-api.js, etc.) and defines the shortcut commands (`npm run dev`, `npm run build`).
- `package-lock.json` — records the *exact* version of every dependency that was installed, so everyone on the team gets identical packages when they run `npm install`.
- `vite.config.ts` — settings for Vite, the tool that runs the dev server and bundles the app for production.
- `postcss.config.mjs` — plugs Tailwind CSS into the build process so the utility classes used throughout the screens (like `bg-gray-50`) actually generate real CSS.

### App setup (`src/`)
- `main.jsx` — the very first file that runs. It grabs the `<div id="root">` from `index.html` and tells React to render the app into it.
- `app/App.tsx` — the top-level component. All it does is hand control over to the router so the correct screen shows up for the current URL.
- `app/routes.js` — the site map. It's a list pairing each URL (like `/dashboard`) with the screen component that should be shown there. **If you're adding a new page, this is the file to update.**

### Screens (`src/app/screens/`) — one file per page in the app
- `LoginScreen.jsx` → `/` — the entry screen with a username/password form. Submitting it (with anything typed in) sends you to the dashboard. No real authentication happens.
- `DashboardScreen.jsx` → `/dashboard` — the home hub after logging in. Shows a status card and a "latest alert" card (both hardcoded), plus a button for each of the four features below.
- `LiveFeedScreen.jsx` → `/live-feed` — **the core feature of the whole prototype.** It opens your webcam feed and, roughly 5 times per second, runs a face-detection AI model over the current video frame. Any face it finds gets a green box drawn around it on top of the video. It also handles what to show if the camera is blocked or the AI model fails to download.
- `EventHistoryScreen.jsx` → `/event-history` — a scrollable list of past "detection events" (e.g. "Unknown individual detected", "Resident identified: John Smith"). The list itself is just an array of sample objects written at the top of the file — it's not pulling from any real camera log.
- `EventDetailScreen.jsx` → `/event-detail/:id` — clicking an event in the history list brings you here to see more info about it (timestamp, classification, a snapshot photo). The `:id` in the URL picks which hardcoded event to display; the "snapshot" is just a placeholder stock photo.
- `RegisterResidentScreen.jsx` → `/register-resident` — a form for adding a new known resident: a name field and buttons to "upload" or "capture" a face photo. Clicking those buttons only changes what the preview box looks like — no actual image is stored anywhere, and there's no connection yet to the face-detection feature.
- `AlertSettingsScreen.jsx` → `/alert-settings` — lets you turn alerts on/off and choose push vs. email notifications. These are just checkboxes/toggles wired to the screen's own local state — nothing is saved to a device, account, or server, so it won't remember your choice next time you open the app.

### Components (`src/app/components/`)
- `figma/ImageWithFallback.tsx` — a small image-rendering helper that was carried over from the original Figma design export. It's used by the Event Detail screen to show the snapshot photo, and shows a fallback graphic if the image fails to load.

### Styles (`src/styles/`)
- `index.css` — the main stylesheet that gets imported once in `main.jsx`; it pulls in all the other style files below.
- `tailwind.css` — the Tailwind CSS setup that powers most of the visual styling you see in the screens (things like `p-4`, `rounded-lg`, `border-gray-300`).
- `theme.css` — shared color and theme variables used across the app.
- `fonts.css` — font declarations/imports.

## Good to know before you dig in

- **Nothing persists.** Refreshing the browser wipes any in-progress state — toggles reset, "uploaded" photos disappear, etc. This is expected; there's no storage layer yet.
- **Live Feed needs two things to work:** camera permission from the browser, and an internet connection (the face-detection model itself is downloaded from a CDN the first time the screen loads, it isn't bundled with the app).
- **Detection ≠ recognition.** Right now the app can tell "a face is present," but it can't yet tell *whose* face it is or match it against a registered resident. That would be the natural next step to build on top of the Live Feed and Register Resident screens.
