"""Main application entry point for KON Media.

Runs on loopback (127.0.0.1:8899), mounts the REST & SSE API,
and serves the production React frontend bundle.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import router as api_router, task_manager
from backend.config import HOST, PORT, FRONTEND_DIST_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: register event loop with task manager and run background self-training."""
    loop = asyncio.get_running_loop()
    task_manager.set_event_loop(loop)

    async def background_startup_training():
        try:
            await asyncio.sleep(1.0)
            from backend.search.engine import SearchEngine
            from backend.storage.storage import HistoryStore
            from backend.config import STATE_DIR
            h_store = HistoryStore(STATE_DIR)
            engine = SearchEngine()
            history_entries = h_store.get_all()
            if history_entries or engine.feedback_store.get_all():
                engine.self_train(download_history=history_entries, epochs=3)
        except Exception:
            pass

    asyncio.create_task(background_startup_training())
    yield


app = FastAPI(
    title="KON Media",
    description="A private, local-first media toolkit for Windows 11",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration supporting local dev and cloud web clients
cors_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8899",
    "http://localhost:8899",
    "https://not-phana.github.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API endpoints
app.include_router(api_router)

# Mount frontend static files if production build exists
if FRONTEND_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Do not serve index.html for unknown /api/ routes
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API endpoint not found.")
        # Serve exact file if it exists, otherwise fallback to index.html for SPA routing
        target = FRONTEND_DIST_DIR / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_DIST_DIR / "index.html"))
else:
    @app.get("/")
    async def dev_index():
        return HTMLResponse(
            """<!DOCTYPE html>
<html>
<head><title>KON Media Backend</title></head>
<body style="background:#17191d; color:#f3f4f6; font-family:sans-serif; padding:40px; text-align:center;">
    <h1 style="color:#8bc5b0;">KON Media API is running</h1>
    <p>Local media processing service is active on <code>127.0.0.1:8899</code>.</p>
    <p>Frontend dev server available on port 5173, or run <code>npm run build</code> in <code>frontend/</code>.</p>
    <p><a href="/docs" style="color:#8bc5b0;">View OpenAPI Documentation</a></p>
</body>
</html>"""
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)
