import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from flakeforge.web.api import router as api_router

app = FastAPI(
    title="FlakeForge Web Dashboard",
    description="Interactive Live Interface for Deterministic Concurrency De-Flaking",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api")

# Mount web UI static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
