# app.py - live Streamlit dashboard for the India AQI pipeline
#
# Reads the dbt analytics tables from whichever database DB_TYPE points to.
# Run locally:  streamlit run dashboard/app.py
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

# Streamlit runs this file from dashboard/, so make the project root importable (for scraper.db_connection)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scraper.db_connection import get_db_type, get_engine  # noqa: E402

CACHE_TTL_SECONDS = 600          # re-query the database at most every 10 minutes
AUTO_REFRESH = "10m"             # rerun the page body every 10 minutes while it is open

# Official CPCB National AQI colours - the scale Indian AQI readers already know.
# Colour is never used alone: every category is also written out as text.
CATEGORY_ORDER = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
CATEGORY_COLORS = {
    "Good": "#009865", "Satisfactory": "#98C11D", "Moderate": "#FFD300",
    "Poor": "#F29C33", "Very Poor": "#E93F33", "Severe": "#AF2D24",
}
# Fixed categorical order for city lines (validated palette; never cycled past 8)
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_TREND_CITIES = len(SERIES_COLORS)

st.set_page_config(page_title="India AQI Live", page_icon="🌫️", layout="wide")


# ---------- data access ----------

@st.cache_resource
def engine():
    return get_engine()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading latest air quality data...")
def query(sql: str) -> pd.DataFrame:
    with engine().connect() as conn:
        df = pd.read_sql(text(sql), conn)
    df.columns = [c.lower() for c in df.columns]     # Snowflake returns UPPERCASE names
    return df


def load_data() -> dict[str, pd.DataFrame]:
    return {
        "latest": query("select * from analytics.city_latest_aqi"),
        "ranking": query("select * from analytics.city_ranking_24h"),
        "hourly": query("""
            select city, state, hour_start_ist, avg_aqi, stations_reporting
            from analytics.fct_city_aqi_hourly
        """),
        "profile": query("select * from analytics.city_hour_of_day_profile"),
        "categories": query("select * from analytics.aqi_category_distribution"),
    }


# ---------- page sections ----------

def kpi_row(latest: pd.DataFrame) -> None:
    worst = latest.loc[latest["avg_aqi"].idxmax()]
    best = latest.loc[latest["avg_aqi"].idxmin()]
    national_avg = latest["avg_aqi"].mean()
    poor_or_worse = latest[latest["avg_aqi"] > 200]
    people_exposed = poor_or_worse["population_2011"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Most polluted city now", f"{worst['city']}", f"AQI {worst['avg_aqi']:.0f} · {worst['aqi_category']}",
              delta_color="off")
    c2.metric("Cleanest city now", f"{best['city']}", f"AQI {best['avg_aqi']:.0f} · {best['aqi_category']}",
              delta_color="off")
    c3.metric("National average AQI", f"{national_avg:.0f}",
              f"{len(latest)} cities · {int(latest['stations_reporting'].sum())} stations", delta_color="off")
    c4.metric("Cities at 'Poor' or worse", f"{len(poor_or_worse)}",
              f"{people_exposed / 1e6:.1f} M people (Census 2011)" if people_exposed else "—", delta_color="off")


def aqi_map(latest: pd.DataFrame) -> None:
    st.subheader("Air quality across India right now")
    fig = px.scatter_map(
        latest.dropna(subset=["latitude", "longitude"]),
        lat="latitude", lon="longitude",
        color="aqi_category", color_discrete_map=CATEGORY_COLORS,
        category_orders={"aqi_category": CATEGORY_ORDER},
        size="stations_reporting", size_max=18,
        hover_name="city",
        hover_data={"avg_aqi": True, "aqi_category": True, "dominant_pollutant": True,
                    "worst_station": True, "stations_reporting": True,
                    "latitude": False, "longitude": False},
        labels={"avg_aqi": "AQI", "aqi_category": "Category", "dominant_pollutant": "Main pollutant",
                "worst_station": "Worst station", "stations_reporting": "Stations"},
        center={"lat": 22.5, "lon": 80}, zoom=3.6, height=560, map_style="carto-positron",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend_title_text="AQI category")
    st.plotly_chart(fig, width="stretch")


def ranking_chart(ranking: pd.DataFrame) -> None:
    st.subheader("Most polluted cities · last 24 hours")
    top = ranking.nsmallest(15, "most_polluted_rank").sort_values("avg_aqi_24h")
    fig = px.bar(top, x="avg_aqi_24h", y="city", orientation="h", text="aqi_category",
                 hover_data={"state": True, "peak_aqi_24h": True, "hours_covered": True},
                 labels={"avg_aqi_24h": "Average AQI (24 h)", "city": "", "peak_aqi_24h": "Peak AQI",
                         "hours_covered": "Hours of data"},
                 height=560, color_discrete_sequence=[SERIES_COLORS[0]])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(margin=dict(l=0, r=60, t=10, b=0), bargap=0.35)
    st.plotly_chart(fig, width="stretch")


def add_category_bands(fig: go.Figure) -> None:
    """Faint dotted lines at the category boundaries so readers can place a value."""
    for value, label in [(100, "Satisfactory | Moderate"), (200, "Moderate | Poor"), (300, "Poor | Very Poor")]:
        fig.add_hline(y=value, line_dash="dot", line_width=1, line_color="rgba(128,128,128,0.5)",
                      annotation_text=label, annotation_position="top left",
                      annotation_font_size=10, annotation_font_color="gray")


def trend_chart(hourly: pd.DataFrame, cities: list[str]) -> None:
    st.subheader("Hourly AQI trend")
    data = hourly[hourly["city"].isin(cities)].sort_values("hour_start_ist")
    if data.empty:
        st.info("No hourly data for the selected cities yet.")
        return
    fig = px.line(data, x="hour_start_ist", y="avg_aqi", color="city",
                  category_orders={"city": cities},
                  color_discrete_sequence=SERIES_COLORS, markers=data["hour_start_ist"].nunique() < 3,
                  labels={"hour_start_ist": "Hour (IST)", "avg_aqi": "Average AQI", "city": "City"},
                  height=420)
    fig.update_traces(line_width=2)
    add_category_bands(fig)
    fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")


def hour_of_day_heatmap(profile: pd.DataFrame, cities: list[str]) -> None:
    st.subheader("When is the air worst? Typical AQI by hour of day (IST)")
    data = profile[profile["city"].isin(cities)]
    if data.empty:
        st.info("Not enough history yet.")
        return
    grid = data.pivot_table(index="city", columns="hour_of_day", values="avg_aqi").reindex(columns=range(24))
    grid = grid.reindex([c for c in cities if c in grid.index])
    fig = px.imshow(grid, color_continuous_scale="Reds", aspect="auto", zmin=0,
                    labels={"x": "Hour of day (IST)", "y": "", "color": "AQI"}, height=120 + 40 * len(grid))
    fig.update_xaxes(dtick=2)
    fig.update_traces(xgap=2, ygap=2,
                      hovertemplate="%{y} at %{x}:00 IST<br>Typical AQI %{z:.0f}<extra></extra>")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
    peaks = data[data["is_peak_hour"]].groupby("city")["hour_of_day"].min()
    if not peaks.empty:
        st.caption("Peak hour: " + " · ".join(f"**{city}** {hour:02d}:00" for city, hour in peaks.items()))


def category_chart(categories: pd.DataFrame, cities: list[str]) -> None:
    st.subheader("How often the air was Good … Severe")
    data = categories[categories["city"].isin(cities)].sort_values("category_order")
    if data.empty:
        st.info("Not enough history yet.")
        return
    fig = px.bar(data, x="share_pct", y="city", color="aqi_category", orientation="h",
                 color_discrete_map=CATEGORY_COLORS, category_orders={"aqi_category": CATEGORY_ORDER, "city": cities},
                 hover_data={"station_hours": True},
                 labels={"share_pct": "% of station-hours", "city": "", "aqi_category": "Category",
                         "station_hours": "Station-hours"},
                 height=140 + 40 * data["city"].nunique())
    fig.update_traces(marker_line_width=2, marker_line_color="rgba(0,0,0,0)")
    fig.update_layout(barmode="stack", margin=dict(l=0, r=0, t=10, b=0), xaxis_range=[0, 100],
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, width="stretch")


# ---------- page ----------

st.title("🌫️ India Air Quality — Live")
st.caption(
    "Hourly CPCB data from data.gov.in → PostgreSQL / Snowflake → dbt → this dashboard. "
    "Source: Central Pollution Control Board via [data.gov.in](https://data.gov.in) (GODL-India). "
    "Population: Wikipedia (CC BY-SA 4.0)."
)


@st.fragment(run_every=AUTO_REFRESH)
def dashboard() -> None:
    try:
        data = load_data()
    except Exception as err:   # noqa: BLE001 - show a friendly message instead of a stack trace
        st.error(f"Could not read from the {get_db_type()} database ({type(err).__name__}). "
                 "Check the connection settings.")
        return

    latest = data["latest"]
    if latest.empty:
        st.warning("No data yet - run the pipeline and `dbt build` first.")
        return

    last_reading = pd.to_datetime(latest["last_reading_ist"]).max()
    st.markdown(f"**Last updated:** {last_reading:%d %b %Y, %H:%M} IST · reading from **{get_db_type()}**")

    kpi_row(latest)
    st.divider()

    left, right = st.columns([3, 2])
    with left:
        aqi_map(latest)
    with right:
        ranking_chart(data["ranking"])

    st.divider()
    # Options = every city with hourly history. The default must be a subset of the options,
    # so pick the most polluted cities (24 h ranking) that are actually in that list.
    city_options = sorted(data["hourly"]["city"].unique())
    worst_first = data["ranking"].sort_values("most_polluted_rank")["city"].drop_duplicates()
    default_cities = [city for city in worst_first if city in city_options][:3]
    cities = st.multiselect(
        f"Compare cities (up to {MAX_TREND_CITIES})", options=city_options,
        default=default_cities, max_selections=MAX_TREND_CITIES,
    )
    if not cities:
        st.info("Pick at least one city.")
        return

    trend_chart(data["hourly"], cities)
    c1, c2 = st.columns(2)
    with c1:
        hour_of_day_heatmap(data["profile"], cities)
    with c2:
        category_chart(data["categories"], cities)

    with st.expander("Data table: current AQI for every city"):
        st.dataframe(
            latest.sort_values("avg_aqi", ascending=False)[
                ["city", "state", "avg_aqi", "aqi_category", "dominant_pollutant", "worst_station",
                 "stations_reporting", "population_2011", "last_reading_ist"]
            ],
            hide_index=True, width="stretch",
        )


dashboard()
