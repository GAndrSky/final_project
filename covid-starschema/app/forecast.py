# app/forecast.py
import os
import math
import pandas as pd
import plotly.express as px

try:
    from prophet import Prophet 
    HAS_PROPHET = True
except Exception:
    HAS_PROPHET = False

from .snow_client import get_conn

REPORT_DIR = "app/static/report"

SQL_FOR_FC = """
WITH sd AS (
  SELECT 
    DATE, 
    SUM(CASES) AS total_cases,
    LAG(SUM(CASES)) OVER (ORDER BY DATE) AS prev_cases
  FROM COVID19_EPIDEMIOLOGICAL_DATA.PUBLIC.NYT_US_COVID19
  WHERE STATE = %s
  GROUP BY DATE
)
SELECT 
  DATE AS ds,
  COALESCE(total_cases - prev_cases, 0) AS y
FROM sd
WHERE ds >= '2020-03-01'
ORDER BY ds;
"""

def _load_series(state: str) -> pd.DataFrame:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(SQL_FOR_FC, (state,))
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        cur.close()
    df = pd.DataFrame(rows, columns=cols)
    df["ds"] = pd.to_datetime(df["DS"])
    df["y"] = pd.to_numeric(df["Y"], errors="coerce").fillna(0)
    df = df[df["y"] >= 0]
    return df[["ds","y"]]

def _forecast_fallback(df: pd.DataFrame, days: int) -> pd.DataFrame:

    df = df.copy()
    df["ma14"] = df["y"].rolling(14, min_periods=1).mean()

    last_date = df["ds"].max()
    last_val  = float(df["ma14"].iloc[-1]) if not math.isnan(df["ma14"].iloc[-1]) else float(df["y"].iloc[-1])

    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=days, freq="D")
    fc = pd.DataFrame({"ds": future_dates, "yhat": [last_val]*days})
    hist = pd.DataFrame({"ds": df["ds"], "yhat": df["ma14"]})
    return pd.concat([hist, fc], ignore_index=True)

def create_forecast(state: str = "California", days: int = 30) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    df = _load_series(state)
    if df.empty:
        raise ValueError(f"No data to forecast for '{state}'")

    if HAS_PROPHET:
        m = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False, changepoint_prior_scale=0.05)
        m.fit(df.rename(columns={"ds":"ds","y":"y"}))
        future = m.make_future_dataframe(periods=days)
        fc = m.predict(future)[["ds","yhat"]]
    else:
        fc = _forecast_fallback(df, days)

    fig = px.line()
    fig.add_scatter(x=df["ds"], y=df["y"], mode="lines", name="Historical")
    fig.add_scatter(x=fc["ds"], y=fc["yhat"], mode="lines", name="Forecast")
    fig.update_layout(
        title=f"COVID‑19 Cases Forecast — {state}",
        xaxis_title="Date",
        yaxis_title="New Cases (predicted)"
    )

    out_html = os.path.join(REPORT_DIR, f"forecast_{state.replace(' ','_')}.html")
    fig.write_html(out_html, include_plotlyjs="cdn")
    return f"/static/report/{os.path.basename(out_html)}"
