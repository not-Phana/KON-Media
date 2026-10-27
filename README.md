# KON Media

A private, local-first media toolkit for Windows 11 engineered for organizing and downloading media from permitted sources with **$0 recurring operating costs**.

Built with **FastAPI**, **React 19**, **Tailwind CSS**, and **yt-dlp**.

---

## Key Principles & Features

* **$0 Recurring Operating Cost**: Runs 100% locally on your Windows 11 desktop. No paid APIs, cloud subscriptions, or server bills.
* **Complete Privacy**: No accounts, registration, ads, telemetry, or third-party cookies.
* **Neumorphic Media Workspace**: Refined dark dashboard design (`#17191D`, `#202329`, `#8BC5B0`) with tactile raised controls and recessed input surfaces meeting WCAG AA contrast standards.
* **Live Download Progress**: Real-time progress updates (percentage, speed, ETA) delivered seamlessly via Server-Sent Events (SSE).
* **Robust Security Controls**: Clean-room URL Guard and SSRF firewall that blocks loopback, cloud metadata endpoints, and RFC1918 private subnets.
* **Windows 11 Native Integration**: Filename sanitization against Windows reserved device names (`CON`, `PRN`), overwrite collision prevention, and native "Open in Folder" File Explorer integration.
* **Zero-Database Persistence**: Atomic JSON storage engine (`app_state/history.json`, `app_state/settings.json`) that protects against file corruption without external database servers.

---

## Quick Start

### 1. Launch with One Click
Double-click `start.bat` in the project root. This starts the local backend service on `127.0.0.1:8899` and automatically opens your browser to the workspace.

### 2. Manual Startup
To run using the Python virtual environment:
```powershell
Set-Location "E:\Code\make thing"
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8899
```
Open **http://127.0.0.1:8899** in your browser.

### 3. Development Mode
To develop frontend and backend with hot reloading:
```powershell
# Terminal 1 - Backend:
Set-Location "E:\Code\make thing"
.\.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8899

# Terminal 2 - Frontend:
Set-Location "E:\Code\make thing\frontend"
npm run dev
```

---

## Project Structure

```
E:\Code\make thing\
├── backend/                  # FastAPI Application
│   ├── api/                  # REST & SSE Router (router.py)
│   ├── engine/               # yt-dlp Media Integration (media_engine.py)
│   ├── security/             # SSRF & URL Guards (url_guard.py)
│   ├── storage/              # Atomic Storage & File Manager (storage.py, file_manager.py)
│   ├── config.py             # System paths and configuration
│   └── main.py               # Uvicorn entry point & SPA server
├── frontend/                 # React 19 + Vite + Tailwind CSS Workspace
│   ├── src/                  # Neumorphic components, hooks, and API client
│   └── dist/                 # Production compiled static bundle
├── downloads/                # Default local media download destination
├── app_state/                # Atomic JSON persistent stores (history, settings)
├── docs/                     # Full technical documentation
│   ├── OPEN-SOURCE-RESEARCH.md
│   ├── DESIGN-SYSTEM.md
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION-PLAN.md
│   ├── SECURITY.md
│   ├── COST-AND-DEPLOYMENT.md
│   └── TESTING.md
├── tests/                    # Automated pytest test suite (23 tests)
├── start.bat                 # One-click Windows desktop launcher
├── requirements.txt          # Python dependencies
└── THIRD-PARTY-LICENSES.md   # Open-source attributions
```

---

## Documentation Index

Detailed technical reports and specifications are available in `docs/`:

1. [Open-Source Research & Candidate Audit](docs/OPEN-SOURCE-RESEARCH.md)
2. [Tactile Neumorphic Design System](docs/DESIGN-SYSTEM.md)
3. [System Architecture & Data Flows](docs/ARCHITECTURE.md)
4. [Master Implementation Plan](docs/IMPLEMENTATION-PLAN.md)
5. [Security Architecture & Threat Model](docs/SECURITY.md)
6. [Cost, Deployment & Operating Model](docs/COST-AND-DEPLOYMENT.md)
7. [Testing & Verification Report](docs/TESTING.md)
8. [Third-Party Licenses & Attributions](THIRD-PARTY-LICENSES.md)

---

## Verification & Tests

To execute the automated test suite:
```powershell
Set-Location "E:\Code\make thing"
.\.venv\Scripts\python -m pytest tests/ -v
```
All 23 security, storage, filesystem, and API tests run and pass in ~1.5s.
