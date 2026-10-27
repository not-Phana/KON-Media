# KON Media — Cost, Deployment & Operating Model

## 1. Zero Recurring Cost Guarantee

**KON Media** is designed from the ground up to achieve **$0 recurring operating cost**:

* **$0 Hosting**: Runs 100% locally on the user's Windows 11 desktop.
* **$0 Cloud Services**: Zero external databases, cloud storage buckets, serverless functions, or proxies.
* **$0 Paid APIs**: All media extraction is performed using the free, open-source `yt-dlp` engine.
* **$0 Subscriptions**: No registration, no user accounts, no premium paywalls, and no telemetry tracking.
* **$0 Licensing Costs**: Built entirely on free and open-source software (MIT, The Unlicense).

---

## 2. System Requirements & Software Stack

### Minimum Requirements
* **Operating System**: Windows 11 (or Windows 10 64-bit).
* **Python**: Python 3.10+ (Verified on Python 3.13.15).
* **Node.js**: Node.js 18+ (Verified on Node.js v24.19.0 with npm 12.0.2).
* **Disk Space**: ~250 MB for application and Python virtual environment; user-configurable storage for media downloads (Verified: 234 GB free on Drive E:).
* **Optional Dependency**: `ffmpeg` (Recommended for merging 1080p+ video with audio and high-quality MP3 conversion).

---

## 3. Deployment Architecture

```
E:\Code\make thing\
├── backend/                  # FastAPI Application
│   ├── api/                  # REST & SSE Endpoints
│   ├── engine/               # yt-dlp Media Integration
│   ├── security/             # SSRF & URL Guards
│   ├── storage/              # Atomic JSON persistence & File Manager
│   └── main.py               # Application entry point
├── frontend/                 # React 19 + Vite + Tailwind CSS Workspace
│   ├── src/                  # Neumorphic UI Components & Hooks
│   └── dist/                 # Production compiled static bundle
├── downloads/                # Default local media download destination
├── app_state/                # Local JSON state (history.json, settings.json)
├── start.bat                 # One-click desktop launcher
└── requirements.txt          # Python dependencies
```

---

## 4. Local Execution & Process Management

### Startup
The application can be launched in two modes:

1. **Production Desktop Mode (Single Server)**:
   The frontend is pre-built into `frontend/dist/`. FastAPI serves the static assets at `http://127.0.0.1:8899/` while simultaneously handling all media API requests.
   ```powershell
   .\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8899
   ```

2. **Development Mode**:
   FastAPI backend runs on port 8899; Vite runs on port 5173 with API proxying:
   * Backend: `uvicorn backend.main:app --reload --port 8899`
   * Frontend: `npm run dev`

### Shutdown
* Press `Ctrl+C` in the terminal to initiate a graceful shutdown.
* Active downloads are signalled to cancel, temporary partial files are cleaned up, and atomic state is flushed to disk.

---

## 5. Storage, Backup & Recovery

* **State Directory (`app_state/`)**:
  * `history.json`: Download task records (timestamps, titles, formats, file sizes, local paths).
  * `settings.json`: User preferences (download directory, max concurrent downloads, default quality).
* **Zero Corruption Guarantee**: All updates use atomic temporary file replacement (`os.replace`), preventing corrupted state files even if the process is killed abruptly.
* **Backup**: To backup the entire application configuration and history, simply copy the `app_state/` folder.
