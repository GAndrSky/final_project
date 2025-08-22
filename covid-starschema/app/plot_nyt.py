import os
import pandas as pd
import plotly.express as px
from snow_client import get_conn

def normalize_df(df):
    df = df.rename(columns=str.lower).copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    for col in ["new_cases", "ma7_new_cases", "new_deaths", "ma7_new_deaths"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df

STATE_INPUT = os.getenv("STATE", "New York").strip()

USPS_TO_NAME = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut",
    "DE":"Delaware","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana",
    "IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts",
    "MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada",
    "NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota",
    "OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina",
    "SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
    "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming","DC":"District of Columbia"
}

def normalize_state(s: str) -> str:
    s = s.strip()
    if len(s) == 2:
        return USPS_TO_NAME.get(s.upper(), s)
    return " ".join(w.capitalize() for w in s.split())

SQL_STATE = """
WITH s AS (
  SELECT
    date, cases, deaths,
    LAG(cases)  OVER (ORDER BY date) AS prev_cases,
    LAG(deaths) OVER (ORDER BY date) AS prev_deaths
  FROM COVID19_EPIDEMIOLOGICAL_DATA.PUBLIC.NYT_US_COVID19
  WHERE state = %s
),
daily AS (
  SELECT
    date,
    COALESCE(cases - prev_cases, cases)      AS new_cases,
    COALESCE(deaths - prev_deaths, deaths)   AS new_deaths
  FROM s
)
SELECT
  date,
  new_cases,
  AVG(new_cases)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_new_cases,
  new_deaths,
  AVG(new_deaths) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_new_deaths
FROM daily
ORDER BY date;
"""

SQL_US = """
WITH c AS (
  SELECT date,
         SUM(cases)  AS cases,
         SUM(deaths) AS deaths
  FROM COVID19_EPIDEMIOLOGICAL_DATA.PUBLIC.NYT_US_COVID19
  GROUP BY date
),
d AS (
  SELECT
    date, cases, deaths,
    LAG(cases)  OVER (ORDER BY date) AS prev_cases,
    LAG(deaths) OVER (ORDER BY date) AS prev_deaths
  FROM c
),
daily AS (
  SELECT
    date,
    COALESCE(cases - prev_cases, cases)      AS new_cases,
    COALESCE(deaths - prev_deaths, deaths)   AS new_deaths
  FROM d
)
SELECT
  date,
  new_cases,
  AVG(new_cases)  OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_new_cases,
  new_deaths,
  AVG(new_deaths) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_new_deaths
FROM daily
ORDER BY date;
"""

def save_plots(df: pd.DataFrame, label: str):
    df = normalize_df(df)
    os.makedirs("report", exist_ok=True)
    fig1 = px.line(df, x="date", y=["new_cases","ma7_new_cases"], title=f"New cases & MA7 — {label}")
    fig1.write_html(f"report/cases_{label}.html", include_plotlyjs="cdn")
    fig2 = px.line(df, x="date", y=["new_deaths","ma7_new_deaths"], title=f"New deaths & MA7 — {label}")
    fig2.write_html(f"report/deaths_{label}.html", include_plotlyjs="cdn")
    print("Saved:", f"report/cases_{label}.html", f"report/deaths_{label}.html")

def main():
    state_name = normalize_state(STATE_INPUT)
    from snow_client import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(SQL_STATE, (state_name,))
        rows = cur.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
            cur.close()
            save_plots(df, state_name.replace(" ", "_"))
            return

        cur.execute(SQL_US)
        df = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
        cur.close()
        save_plots(df, "US_total")

if __name__ == "__main__":
    main()