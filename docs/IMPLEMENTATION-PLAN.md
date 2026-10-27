# KON Media — Master Implementation Plan

## 1. Overview & Phasing Roadmap

This plan outlines the staged, verifiable development of **KON Media**, a local-first media toolkit for Windows 11 built with Python (FastAPI), React 19, Tailwind CSS, and `yt-dlp`.

---

## 2. Phase-by-Phase Roadmap

### Phase 0: Research, Planning & Specifications (Completed)
- [x] Environment inspection at `E:\Code\make thing` (Node v24.19.0, npm 12.0.2, Python 3.13.15, Git 2.55.0, 234 GB free on Drive E:).
- [x] Research candidate projects (`reclip`, `yt-dlp-web`, `metube`, upstream `yt-dlp`) in `research/candidates/`.
- [x] Author `docs/OPEN-SOURCE-RESEARCH.md` with architectural comparison and licensing assessment.
- [x] Author `docs/DESIGN-SYSTEM.md` establishing the Neumorphic Media Workspace specifications.
- [x] Author `docs/ARCHITECTURE.md` defining component boundaries and data flows.
- [x] Author `docs/SECURITY.md` establishing threat model and URL/SSRF/path guards.
- [x] Author `docs/COST-AND-DEPLOYMENT.md` confirming $0 recurring cost model.

### Phase 1: Foundation Setup
- [ ] Initialize Python virtual environment (`.venv`) on Drive E: and install core dependencies (`fastapi`, `uvicorn`, `yt-dlp`, `pydantic`, `pytest`, `httpx`).
- [ ] Scaffold FastAPI backend structure (`backend/` with routers, storage, engine, security).
- [ ] Scaffold React 19 + Vite + Tailwind CSS frontend (`frontend/`) configured with custom Neumorphic tokens, shadows, and Lucide icons.
- [ ] Implement initial health and environment verification endpoints (`GET /api/health`).
- [ ] Establish automated unit test runner (`pytest`).

### Phase 2: Functional Media Workflow
- [ ] Implement `url_guard.py` for SSRF protection and scheme validation.
- [ ] Implement `media_engine.py` wrapping `yt_dlp.YoutubeDL` for safe metadata extraction.
- [ ] Implement `task_manager.py` with asynchronous download execution, state tracking, and thread-safe cancellation.
- [ ] Implement Server-Sent Events (SSE) router (`GET /api/events`) streaming real-time download progress (percentage, speed, ETA).
- [ ] Implement `file_manager.py` with Windows filename sanitization and overwrite protection.
- [ ] Implement URL analysis endpoint (`POST /api/analyze`) and download creation endpoint (`POST /api/download`).

### Phase 3: Neumorphic Personal Workspace
- [ ] Implement Neumorphic UI components in React:
  - Header with system status indicators (yt-dlp status, ffmpeg status).
  - Recessed URL input bar with paste button and analyze trigger.
  - Media info card with thumbnail, duration badge, title, channel, and format selector tabs (Video / Audio).
  - Active download task cards with real-time animated progress bars, speed, ETA, and cancel action.
  - Local history table with status badges and "Open in Folder" action.
  - Settings panel (custom download path, concurrent download limit).
- [ ] Implement atomic JSON persistence (`storage.py`) for `history.json` and `settings.json`.
- [ ] Native Windows Explorer integration (`POST /api/open-folder`).

### Phase 4: Reliability, Security Hardening & Edge Cases
- [ ] Write security tests for URL validation (blocking SSRF, internal IPs, malformed URLs, command injection vectors).
- [ ] Write tests for filename sanitization (Windows reserved names, traversal sequences, length truncation).
- [ ] Write tests for download cancellation and temporary file cleanup.
- [ ] Verify graceful degradation when `ffmpeg` is absent (clear warning informing user of limitations without crashing).
- [ ] Verify accessibility (WCAG AA contrast, keyboard navigation, focus outlines, reduced motion).

### Phase 5: Production Build & Verification
- [ ] Build production frontend (`npm run build`) into `frontend/dist/`.
- [ ] Configure FastAPI to serve the production SPA bundle seamlessly on root `/`.
- [ ] Create convenient one-click launcher `start.bat` for Windows 11 desktop usage.
- [ ] Finalize `README.md`, `THIRD-PARTY-LICENSES.md`, and `docs/TESTING.md`.
- [ ] Run full test suite and verify end-to-end functionality.

---

## 3. Verification Criteria & Deliverables
Every phase requires automated test execution and verification before moving to the next phase. Zero unverified mock results or claims.
