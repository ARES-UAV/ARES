"""ARES dashboard API.

The backend serves pre-computed detections against a playback clock — it does
not run inference. See CLAUDE.md, "Demo-day constraints".
"""

import json
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.schemas import Detection, Health

VERSION = "0.1.0"

app = FastAPI(
    title="ARES Dashboard API",
    description="Serves pre-computed survivor detections to the command dashboard.",
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=Health)
def health() -> Health:
    """Liveness check. The dashboard uses this for its connection indicator."""
    return Health(status="ok", service="ares-backend", version=VERSION)


@app.get("/api/detections", response_model=List[Detection])
def detections() -> List[Detection]:
    """Every detection record for the loaded clip, in frame order.

    Read from disk per request rather than cached at startup: the file is a few
    hundred KB, and regenerating the fixture during development shows up
    immediately instead of needing a server restart.
    """
    path = config.FIXTURE_PATH
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No detections file at {path.name}. Generate the development "
                f"fixture with: python tools/make_fixture.py > {path}"
            ),
        )

    try:
        with path.open() as f:
            records = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail=f"{path.name} is not valid JSON: {exc}"
        ) from exc

    return [Detection.model_validate(r) for r in records]
