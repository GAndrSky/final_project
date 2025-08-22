from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .snow_client import get_conn
from .mongo_client import get_mongo
from .cache import ttl_cache
from .eda import run_eda_for_state
from .forecast import create_forecast

SNOW_OFFLINE = os.getenv("SNOWFLAKE_OFFLINE", "0").lower() in ("1", "true", "yes")

class CommentIn(BaseModel):
    name: str
    comment: str
    state: Optional[str] = None
    tags: Optional[list[str]] = None

app = FastAPI(title="US COVID Dashboard API")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def index():
    return FileResponse("app/static/index.html")

SQL_STATE = """
SELECT
  date,
  new_cases,
  AVG(new_cases)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  AS ma7_new_cases,
  new_deaths,
  AVG(new_deaths) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_new_deaths
FROM COVID_DB.MARTS.V_DAILY_STATES
WHERE state = %s
ORDER BY date;
"""

SQL_US = """
SELECT
  date,
  new_cases,
  AVG(new_cases)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  AS ma7_new_cases,
  new_deaths,
  AVG(new_deaths) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_new_deaths
FROM COVID_DB.MARTS.V_DAILY_US
ORDER BY date;
"""

SQL_RATES = """
SELECT
  date,
  new_cases_per_100k,
  AVG(new_cases_per_100k)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  AS ma7_cases_per_100k,
  new_deaths_per_100k,
  AVG(new_deaths_per_100k) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_deaths_per_100k
FROM COVID_DB.MARTS.V_DAILY_STATES_PER100K
WHERE state = %s
ORDER BY date;
"""

SQL_WAVES = """
SELECT state, wave_start, wave_end, wave_len
FROM COVID_DB.MARTS.V_STATE_WAVES
WHERE state = %s
ORDER BY wave_start;
"""

FALLBACK_DIR = Path("app/static/data")

def _load_fallback_us():
    f = FALLBACK_DIR / "us.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

def _load_fallback_state(state: str):
    safe = state.replace(" ", "_")
    f = FALLBACK_DIR / "states" / f"{safe}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

@app.get("/health")
def health():
    return {"status": "ok"}

@ttl_cache(seconds=300)
def _query_state(state: str):
    if SNOW_OFFLINE:
        fb = _load_fallback_state(state)
        return fb or []
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(SQL_STATE, (state,))
            cols = [c[0].lower() for c in cur.description]
            rows = cur.fetchall()
            cur.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        fb = _load_fallback_state(state)
        if fb is not None:
            return fb
        raise HTTPException(status_code=503, detail=f"Snowflake unavailable: {getattr(e, 'msg', str(e))}")

@ttl_cache(seconds=300)
def _query_us():
    if SNOW_OFFLINE:
        fb = _load_fallback_us()
        return fb or []
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(SQL_US)
            cols = [c[0].lower() for c in cur.description]
            rows = cur.fetchall()
            cur.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        fb = _load_fallback_us()
        if fb is not None:
            return fb
        raise HTTPException(status_code=503, detail=f"Snowflake unavailable: {getattr(e, 'msg', str(e))}")

@ttl_cache(seconds=300)
def _query_rates(state: str):
    if SNOW_OFFLINE:
        return []
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(SQL_RATES, (state,))
            cols = [c[0].lower() for c in cur.description]
            rows = cur.fetchall()
            cur.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Snowflake unavailable: {getattr(e, 'msg', str(e))}")

@ttl_cache(seconds=300)
def _query_waves(state: str):
    if SNOW_OFFLINE:
        return []
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(SQL_WAVES, (state,))
            cols = [c[0].lower() for c in cur.description]
            rows = cur.fetchall()
            cur.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Snowflake unavailable: {getattr(e, 'msg', str(e))}")

@app.get("/cases")
def cases(state: str = Query("New York", description="State name, e.g. 'New York'")):
    data = _query_state(state)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for state '{state}'")
    return JSONResponse(content=jsonable_encoder(data))

@app.get("/cases/us")
def cases_us():
    return JSONResponse(content=jsonable_encoder(_query_us()))

@app.get("/rates")
def rates(state: str = Query("New York", description="State name, e.g. 'New York'")):
    data = _query_rates(state)
    if not data:
        raise HTTPException(status_code=404, detail=f"No per-100k data for state '{state}'")
    return JSONResponse(content=jsonable_encoder(data))

@app.get("/patterns")
def patterns(state: str = Query("New York", description="State name, e.g. 'New York'")):
    return JSONResponse(content=jsonable_encoder(_query_waves(state)))

@app.get("/comments")
def get_comments(state: Optional[str] = None):
    db = get_mongo()
    q = {"state": state} if state else {}
    docs = list(db.comments.find(q, {"_id": 0}))
    return JSONResponse(content=jsonable_encoder(docs))

@app.post("/comments")
def post_comment(payload: CommentIn = Body(...)):
    db = get_mongo()
    doc = jsonable_encoder(payload)
    db.comments.insert_one(doc)
    return {"ok": True}

@app.post("/eda")
def eda_run(payload: dict = Body(...)):
    """
    Body: {"state": "California"}
    Returns links to: daily_cases, daily_deaths, csv
    """
    state = (payload.get("state") or "California").strip()
    try:
        urls = run_eda_for_state(state)
        return {"ok": True, "urls": urls}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/forecast")
def forecast_run(payload: dict = Body(...)):
    """
    Body: {"state": "California", "days": 30}
    Returns link to forecast html (Prophet if available, otherwise fallback)
    """
    state = (payload.get("state") or "California").strip()
    days = int(payload.get("days") or 30)
    try:
        url = create_forecast(state, days)
        return {"ok": True, "url": url}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
