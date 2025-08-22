# US COVID Dashboard — Snowflake + FastAPI + Mongo + Plotly

Interactive dashboard for US COVID-19 data (NYT dataset in Snowflake), with user comments (MongoDB), automatic EDA, and forecasting.

## Features
- Daily **cases** and **deaths** (US + by state) with 7-day MA
- Normalized metrics **per 100k**
- Wave detection (growth periods)
- **Comments** (MongoDB)
- **EDA** (HTML charts + CSV export)
- **Forecast** (Prophet with safe fallback)
- **Offline mode** (run without Snowflake using JSON files)
- One-shot **Snowflake setup** script and **Secure Data Sharing**

---

## Tech stack
- Backend: FastAPI (Uvicorn)
- Data: Snowflake (Marketplace → NYT US COVID dataset)
- DB (NoSQL): MongoDB (comments)
- Frontend: Static HTML/CSS/JS + Plotly
- Packaging: Docker Compose

---

## Repository structure
```
covid-platform/
├─ app/
│  ├─ api.py
│  ├─ cache.py
│  ├─ eda.py
│  ├─ forecast.py
│  ├─ mongo_client.py
│  ├─ snow_client.py
│  └─ static/
│     ├─ index.html
│     ├─ style.css
│     ├─ app.js
├─ docker-compose.yml
├─ requirements.txt
├─ .dockerignore
├─ .gitignore
├─ .env.example                 # sample env vars (no secrets)
├─ setup.sql                    # Snowflake one-shot setup
└─ README.md
```

---

## Quick start (Docker — easiest)

```bash
# 1) Clone and enter the project
git clone (https://github.com/GAndrSky/final_project) covid-platform
cd covid-platform

# 2) Copy env template
cp .env.example .env
# For a no-Snowflake demo, set SNOWFLAKE_OFFLINE=1 in .env
# and ensure app/static/data/* exists (see "Offline mode").

# 3) Run
docker compose up --build
```

Open:
- Dashboard → http://localhost:8000/
- API docs (Swagger) → http://localhost:8000/docs
- Health → http://localhost:8000/health

---

## Environment variables (`.env.example`)

```env
# --- Snowflake ---
SNOWFLAKE_ACCOUNT=your_account_locator_or_full_id   # e.g., mz18703.us-east-2.aws
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=WH_COVID
SNOWFLAKE_DATABASE=COVID_DB
SNOWFLAKE_SCHEMA=MARTS
SNOWFLAKE_ROLE=ACCOUNTADMIN

# Offline mode (use JSON files from app/static/data/*)
SNOWFLAKE_OFFLINE=0

# --- MongoDB ---
MONGO_URL=mongodb://mongo:27017
MONGO_DB=covid_app
```

> Do **not** commit `.env`. Ship only `.env.example`.

---

## API endpoints

- `GET /cases?state=New%20York` — state time series (daily + MA7)
- `GET /cases/us` — US time series
- `GET /rates?state=New%20York` — per-100k metrics (daily + MA7)
- `GET /patterns?state=New%20York` — detected growth “waves”
- `GET /comments`, `POST /comments`
- `POST /eda` — builds HTML charts + CSV
- `POST /forecast` — builds forecast HTML
- Docs: `/docs`

Quick checks:
```bash
curl http://localhost:8000/health
curl "http://localhost:8000/cases?state=New%20York"
curl "http://localhost:8000/cases/us"
curl "http://localhost:8000/comments"
```

---

## Snowflake setup (one-shot)

Run **`setup.sql`** in Snowflake with a role that can create/alter objects (e.g., `ACCOUNTADMIN`). It creates:

- `COVID_DB` with schemas `MARTS`, `RAW`, `PUBLIC`
- `DIM_STATES` (population; sample rows included)
- Views: `V_DAILY_US`, `V_DAILY_STATES`, `V_DAILY_STATES_PER100K`, `V_STATE_WAVES`
- Optional: warehouse settings & resource monitor
- Grants


## Troubleshooting

**Snowflake account locked / frequent connections**  
Reset password/unlock user in Snowflake; update `.env`. Temporarily use `SNOWFLAKE_OFFLINE=1` with offline JSON.

**`Object does not exist` / grants fail**  
Use fully qualified names (e.g., `COVID_DB.MARTS.V_DAILY_US`). Do grants with `SECURITYADMIN` or owner role.

**Share not visible / region mismatch**  
Confirm consumer account ID and region. Shares are region-scoped.

**No per-100k for some states**  
Load more rows into `DIM_STATES` (Census population) and rebuild CTAS tables if needed.

**Mongo not reachable (local)**  
In Docker it’s bundled. For local runs without Docker, install Mongo locally or point `MONGO_URL` to an Atlas instance.

**Port already in use**  
Change `--port` in the Uvicorn command or free the port.




