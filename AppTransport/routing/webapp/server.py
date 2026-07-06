"""Mobile-style web GUI for the offline routing + cost engine.

Serves a phone-framed single page (MapLibre GL JS + local PMTiles basemap) and a
small JSON API backed by the routing engine. Run from AppTransport/routing:

    .venv/Scripts/python.exe -m uvicorn webapp.server:app --host 127.0.0.1 --port 8800

then open http://127.0.0.1:8800
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from apptransport_routing.tools import ToolRunner

ROUTING_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
CACHE_DIR = ROUTING_DIR / "cache"
# Reuse the Android app's offline map assets (pmtiles + glyphs + sprite)
ASSETS_DIR = ROUTING_DIR.parent / "app" / "src" / "main" / "assets"

app = FastAPI(title="One M Transport")
_runner: ToolRunner | None = None


def runner() -> ToolRunner:
    global _runner
    if _runner is None:
        _runner = ToolRunner.from_cache(CACHE_DIR)
    return _runner


@app.on_event("startup")
def _warm() -> None:
    runner()  # load the graph once at boot so the first request is fast


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/vehicles")
def vehicles() -> JSONResponse:
    return JSONResponse(runner().dispatch("list_vehicle_types", {}))


@app.get("/api/geocode")
def geocode(q: str, limit: int = 6) -> JSONResponse:
    return JSONResponse(runner().dispatch("geocode_place", {"query": q, "limit": limit}))


class PlanRequest(BaseModel):
    origin: str | dict
    destination: str | dict
    vehicle_type: str = "6wheel"
    round_trip: bool = False
    fuel_surcharge_pct: float = 0.0
    optimize: str = "time"


@app.post("/api/plan")
def plan(req: PlanRequest) -> JSONResponse:
    out = runner().dispatch("plan_transport", req.model_dump())
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return JSONResponse(out)


# Static app files and offline map assets. StaticFiles answers HTTP Range
# requests, which the browser PMTiles reader needs for the 372MB archive.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
