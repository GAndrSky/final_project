# app/eda.py
import os
import pandas as pd
import plotly.express as px
from .snow_client import get_conn 

REPORT_DIR = "app/static/report"

SQL_STATE = """
WITH state_data AS (
  SELECT 
    DATE, 
    SUM(CASES)  AS total_cases, 
    SUM(DEATHS) AS total_deaths,
    LAG(SUM(CASES))  OVER (ORDER BY DATE)  AS prev_cases,
    LAG(SUM(DEATHS)) OVER (ORDER BY DATE)  AS prev_deaths
  FROM COVID19_EPIDEMIOLOGICAL_DATA.PUBLIC.NYT_US_COVID19
  WHERE STATE = %s
  GROUP BY DATE
)
SELECT 
  DATE,
  total_cases,
  total_deaths,
  COALESCE(total_cases - prev_cases, 0)  AS new_cases,
  COALESCE(total_deaths - prev_deaths, 0) AS new_deaths
FROM state_data
ORDER BY DATE;
"""

def run_eda_for_state(state: str = "California") -> dict:
    os.makedirs(REPORT_DIR, exist_ok=True)

    with get_conn() as conn:
       
        cur = conn.cursor()
        cur.execute(SQL_STATE, (state,))
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        cur.close()
    df = pd.DataFrame(rows, columns=cols)

    if df.empty:
        raise ValueError(f"No data for state '{state}'")

    fig_cases = px.line(
        df, x="DATE", y=["NEW_CASES"],
        title=f"Daily New Cases — {state}",
        labels={"DATE":"Date","value":"Count","variable":""}
    )
    cases_html = os.path.join(REPORT_DIR, f"eda_daily_cases_{state.replace(' ','_')}.html")
    fig_cases.write_html(cases_html, include_plotlyjs="cdn")

    fig_deaths = px.line(
        df, x="DATE", y=["NEW_DEATHS"],
        title=f"Daily New Deaths — {state}",
        labels={"DATE":"Date","value":"Count","variable":""}
    )
    deaths_html = os.path.join(REPORT_DIR, f"eda_daily_deaths_{state.replace(' ','_')}.html")
    fig_deaths.write_html(deaths_html, include_plotlyjs="cdn")

    csv_path = os.path.join(REPORT_DIR, f"eda_{state.replace(' ','_')}.csv")
    df.to_csv(csv_path, index=False)

    return {
        "daily_cases": f"/static/report/{os.path.basename(cases_html)}",
        "daily_deaths": f"/static/report/{os.path.basename(deaths_html)}",
        "csv": f"/static/report/{os.path.basename(csv_path)}",
    }
