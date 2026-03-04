"""Streamlit dashboard for Zerobus demo - shows live sensor events."""

import os
import time

import plotly.express as px
import pandas as pd
import streamlit as st
from databricks import sql as dbsql
from databricks.sdk.core import Config

WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
TABLE = "startups_catalog.dw_zerobus.zerobus_events"
REFRESH_INTERVAL = 5  # seconds

cfg = Config()


@st.cache_resource
def get_connection():
    return dbsql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def query(sql: str):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return cols, rows


st.set_page_config(page_title="Zerobus Demo", layout="wide")
st.title("Zerobus Ingest Demo")
st.caption(f"Auto-refreshes every {REFRESH_INTERVAL}s | Table: `{TABLE}`")

# KPIs
kpi_cols, kpi_rows = query(f"""
    SELECT
        COUNT(*) AS total_events,
        COUNT(DISTINCT device_id) AS unique_devices,
        ROUND(AVG(metric_value), 2) AS avg_metric
    FROM {TABLE}
""")

if kpi_rows:
    total, devices, avg_val = kpi_rows[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Events", f"{total:,}")
    c2.metric("Unique Devices", devices)
    c3.metric("Avg Metric Value", avg_val)

# Charts
chart_cols, chart_rows = query(f"""
    SELECT ts, device_id, metric_value, status
    FROM {TABLE}
    ORDER BY ts DESC
    LIMIT 500
""")

if chart_rows:
    df = pd.DataFrame(chart_rows, columns=chart_cols)
    df["ts"] = pd.to_datetime(df["ts"])

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Status Distribution")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig_pie = px.pie(
            status_counts,
            names="status",
            values="count",
            color="status",
            color_discrete_map={"OK": "#2ecc71", "WARN": "#f1c40f", "CRITICAL": "#e74c3c"},
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        st.subheader("Metric Value Over Time")
        fig_scatter = px.scatter(
            df,
            x="ts",
            y="metric_value",
            color="device_id",
            labels={"ts": "Timestamp", "metric_value": "Metric Value", "device_id": "Device"},
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# Recent events table
st.subheader("Recent Events")
tbl_cols, tbl_rows = query(f"""
    SELECT device_id, ts, metric_value, status
    FROM {TABLE}
    ORDER BY ts DESC
    LIMIT 100
""")

if tbl_rows:
    st.dataframe(
        pd.DataFrame(tbl_rows, columns=tbl_cols),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No events yet. Start the producer to see data.")

# Auto-refresh
time.sleep(REFRESH_INTERVAL)
st.rerun()
