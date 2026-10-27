# Open-Source Media Processing Research & Architecture Evaluation

## Executive Summary

To build **KON Media** as a reliable, maintainable, local-first personal media toolkit on Windows 11 with $0 recurring operating costs, we conducted a rigorous inspection of three candidate open-source projects alongside the upstream `yt-dlp` engine.

All repositories were cloned into a segregated research workspace (`research/candidates/`) and analyzed at the source level—inspecting dependency manifests, backend handlers, process management, frontend architecture, and licensing terms.

---

## Candidate Analysis

### Candidate A: ReClip (`averygan/reclip`)

* **Repository**: `https://github.com/averygan/reclip`
* **License**: MIT License (Permissive; allows modification and commercial/personal use with copyright notice).
* **Stack**:
  * **Backend**: Python 3.8+ with Flask (`app.py`, ~150 lines).
  * **Frontend**: Single-file vanilla HTML/CSS/JS (`templates/index.html`) using Jinja2 rendering.
  * **Engine**: CLI invocation of `yt-dlp` and `ffmpeg` via `subprocess.run()`.
* **Key Implementation Details**:
  * `POST /api/info`: Calls `yt-dlp --no-playlist -j <url>`, parses stdout JSON line-by-line (`parse_ytdlp_json`). Extracts unique resolutions by `height` and highest bitrate `tbr`.
  * `POST /api/download`: Generates a random 10-char hex UUID, spawns a daemon thread running `subprocess.run(["yt-dlp", ...])` to download to a local `downloads/` directory.
  * `GET /api/status/<job_id>`: Simple polling endpoint checking an in-memory `jobs` dictionary.
  * `GET /api/file/<job_id>`: Serves the downloaded file with `send_file`.
* **Strengths**:
  * Minimal dependencies (`flask`, `yt-dlp`).
  * Simple, readable single-file architecture.
  * Clean JSON format filtering logic.
* **Limitations & Risks**:
  * **No Real Download Progress**: Uses blocking `subprocess.run()`; cannot report real-time percentage, transfer speed, or ETA.
  * **Ephemeral In-Memory State**: Active jobs are lost if the server restarts.
  * **No Cancellation**: Background threads cannot be cancelled once spawned.
  * **No SSRF / URL Validation**: Accepts arbitrary URLs directly, exposing local network or loopback endpoints.
  * **No Concurrency Controls**: Unbounded thread creation upon multiple user requests.

---

### Candidate B: yt-dlp-web (`samrtulethtb/yt-dlp-web`)

* **Repository**: `https://github.com/samrtulethtb/yt-dlp-web`
* **License**: **NO LICENSE FILE**. Under international copyright law, the code remains "all rights reserved" by default. Direct copying of code from this repository is legally prohibited.
* **Stack**:
  * **Backend**: Python 3.9+ with FastAPI & Uvicorn (`main.py`, ~200 lines).
  * **Frontend**: Vanilla HTML/CSS/JS served via `FastAPI.staticfiles` (`frontend/index.html`).
  * **Engine**: CLI invocation of `yt-dlp` wrapped in `asyncio.to_thread(subprocess.run)`.
* **Key Implementation Details**:
  * Exposes FastAPI REST endpoints (`/api/info`, `/api/download`, `/api/health`).
  * In `/api/download`, creates a temporary directory with `tempfile.mkdtemp()`, runs `yt-dlp`, verifies file size does not exceed `MAX_SIZE_MB`, and returns a `FileResponse` while scheduling directory deletion via FastAPI `BackgroundTasks`.
* **Strengths**:
  * Asynchronous web framework (FastAPI) with Pydantic request models.
  * Health check endpoint verifying `yt-dlp` availability.
  * Temporary file cleanup via `BackgroundTasks`.
* **Limitations & Risks**:
  * **Licensing Blocker**: Lack of an open-source license prevents code reuse.
  * **Blocking HTTP Download**: The `/api/download` request blocks until the entire video is downloaded and merged. If network drops or a large file takes 10 minutes, the browser HTTP request times out.
  * **Open CORS**: Configured with `allow_origins=["*"]` by default.
  * **Cookie File Exposure**: Reads `COOKIES_FILE` from working directory without permission safeguards.

---

### Candidate C: MeTube (`alexta69/metube`)

* **Repository**: `https://github.com/alexta69/metube`
* **License**: **GNU Affero General Public License v3 (AGPL-3.0)**. Strong copyleft: copying or incorporating MeTube source code would compel KON Media to be licensed under AGPL-3.0 and provide full source distribution to any network user.
* **Stack**:
  * **Backend**: Python 3.13 with `aiohttp`, `python-socketio`, and direct `yt_dlp` library integration (`app/main.py`, `app/ytdl.py`).
  * **Frontend**: Angular SPA managed with `pnpm` (`ui/`).
  * **Persistence**: Custom `AtomicJsonStore` (`app/state_store.py`).
  * **Security**: Dedicated SSRF and socket firewall (`app/url_guard.py`).
* **Key Implementation Details**:
  * **Direct Python API**: Directly instantiates `yt_dlp.YoutubeDL(ydl_opts)` with custom loggers (`_DownloadYtdlLogger`, `_ExtractYtdlLogger`) and real-time `progress_hooks`.
  * **Atomic File Storage**: Writes JSON state files atomically using temporary files and atomic renames to prevent corruption without an external database.
  * **Security Hardening**: `url_guard.py` validates URLs at ingress and installs socket-level hooks to block DNS rebinding and internal network probing (loopback, RFC1918, cloud metadata IPs).
* **Strengths**:
  * Production-grade `yt_dlp` Python library integration.
  * Real-time download progress and status transitions.
  * Resilient zero-database atomic persistence.
  * Thorough URL guard and SSRF prevention.
* **Limitations for KON Media**:
  * **AGPL-3.0 Contamination**: Cannot copy or link MeTube code without inheriting AGPL-3.0 copyleft obligations. Must use a clean-room implementation.
  * **Heavy Architecture**: Angular SPA + pnpm workspace + socket.io is unnecessarily heavy and complex for a personal desktop utility on Windows 11.

---

### Upstream yt-dlp (`yt-dlp/yt-dlp`)

* **Repository**: `https://github.com/yt-dlp/yt-dlp`
* **License**: **The Unlicense** (Public Domain Dedication). Free for any purpose, non-commercial or commercial.
* **Capabilities**:
  * Supports extraction from thousands of authorized media sources.
  * Exposes both a rich CLI and a comprehensive Python package (`yt_dlp`).
  * Supports programmatic `progress_hooks` returning exact downloaded bytes, total bytes, speed, ETA, and elapsed time.
  * Robust format selection syntax (`bestvideo+bestaudio/best`, specific format IDs, audio-only extraction).
  * Direct FFmpeg post-processor integration for remuxing and audio extraction.

---

## Architectural Comparison Matrix

| Criteria | Candidate A (ReClip) | Candidate B (yt-dlp-web) | Candidate C (MeTube) | KON Media Target Architecture |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Framework** | Flask | FastAPI | aiohttp + Socket.io | **FastAPI + Uvicorn** |
| **Frontend Stack** | Vanilla JS / Jinja | Vanilla JS | Angular SPA (pnpm) | **React 19 + Vite + Tailwind CSS** |
| **yt-dlp Integration** | CLI (`subprocess.run`) | CLI (`subprocess.run`) | Python library (`yt_dlp`) | **Direct `yt_dlp` Python API + Process Runner** |
| **Progress Reporting** | None (indeterminate) | None (indeterminate) | Real-time (Socket.IO) | **Real-time (Server-Sent Events / SSE)** |
| **Persistence** | None (in-memory) | None | Atomic JSON Store | **Atomic JSON Store (zero DB)** |
| **Security Controls** | None | Basic size check | URL Guard + Socket hook | **URL Guard (SSRF/Local Block) + Sanitizer** |
| **License** | MIT | No License | AGPL-3.0 | **Clean-room MIT (compliant with Unlicense)** |
| **Windows 11 Readiness** | Fair | Fair | Linux/Docker-centric | **Native Windows 11 Desktop First** |

---

## Selected Architecture for KON Media

### 1. Backend: Python 3.13 + FastAPI + Uvicorn
* **Clean-room Implementation**: Clean design inspired by the best patterns (FastAPI typed models, atomic JSON persistence, and direct `yt_dlp` progress hooks) without copying proprietary or AGPL-3.0 code.
* **Direct `yt_dlp` Python Integration**: Use `yt_dlp.YoutubeDL` with asynchronous execution in worker threads (`asyncio.to_thread`). Real-time progress updates are emitted through a thread-safe event queue.
* **Real-time Communication**: Native Server-Sent Events (SSE) via `EventSource`. Eliminates the need for heavyweight WebSocket libraries while providing continuous progress (speed, ETA, percentage, bytes).
* **Security & URL Guard**:
  * Ingress URL parsing with scheme restriction (`http`, `https` only).
  * Loopback & SSRF block: reject `127.0.0.1`, `localhost`, `::1`, `169.254.169.254`, `metadata.google.internal`, and RFC1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
  * Filename sanitization protecting against Windows path traversal (`..`), directory separators, and reserved names (`CON`, `PRN`, `AUX`, `NUL`).
  * Strict loopback binding (`127.0.0.1`).
* **Zero-Database Persistence**:
  * Atomic JSON file store (`app_state/history.json` and `app_state/settings.json`) utilizing temp-write + atomic replace semantics.

### 2. Frontend: React 19 + Vite + Tailwind CSS + Lucide Icons
* **Tactile Neumorphic Design**: Built according to `docs/DESIGN-SYSTEM.md`—dark dashboard workspace with soft recessed inputs, raised interactive buttons, high-contrast states, and crisp typography.
* **Single Page Workspace**: URL analysis card, format/quality inspector, active queue with live progress cards, and local download history.
* **Zero Build Overhead for End User**: Vite compiles the frontend into static assets served directly by FastAPI under `/`, or run via Vite dev server during development.

---

## Conclusion

By selecting a clean-room FastAPI + React/Tailwind architecture, KON Media achieves:
1. **$0 Operating Cost**: 100% local execution on the user's Windows 11 PC.
2. **Full Legal Compliance**: Free from AGPL copyleft viral triggers or unlicensed code.
3. **Superior User Experience**: Real-time progress bars, tactile neumorphic UI, format selection, and cancelable downloads.
4. **Desktop Safety**: Strict SSRF guard, structured arguments, loopback isolation, and atomic file persistence.
