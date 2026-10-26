from __future__ import annotations

import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import boto3
import pandas as pd
import plotly.express as px
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError


st.set_page_config(
    page_title="RailPulse | Indian Rail Analytics",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink: #152b3c; --muted: #748494; --teal: #087f8c; --line: #e6edf1; }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: #f5f8fa; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; color: var(--ink); }
    .block-container { padding-top: 2.1rem; padding-bottom: 3rem; max-width: 1440px; }
    [data-testid="stSidebar"] { background: #102b3a; }
    [data-testid="stSidebar"] * { color: #edf5f6; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #b2c5cb; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 18px 20px; }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); font-family: 'Space Grotesk', sans-serif; }
    div[data-testid="stTabs"] button { font-weight: 600; }
    .eyebrow { color: var(--teal); font-size: .76rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
    .subtle { color: var(--muted); }
    .status-pill { display: inline-block; padding: 6px 11px; border-radius: 999px; background: #e5f5ef; color: #18734e; font-size: .8rem; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _setting(name: str, *, section: str | None = None, default: str = "") -> str:
    env_value = os.getenv(name)
    if env_value:
        return env_value
    try:
        values: Any = st.secrets
        if section:
            values = values.get(section, {})
        value = values.get(name, default)
        return str(value) if value is not None else default
    except (FileNotFoundError, AttributeError):
        return default


def _aws_client(region: str):
    access_key = _setting("AWS_ACCESS_KEY_ID", section="aws") or _setting(
        "access_key_id", section="aws"
    )
    secret_key = _setting("AWS_SECRET_ACCESS_KEY", section="aws") or _setting(
        "secret_access_key", section="aws"
    )
    session_token = _setting("AWS_SESSION_TOKEN", section="aws") or _setting(
        "session_token", section="aws"
    )
    client_args: dict[str, str] = {"region_name": region}
    if access_key and secret_key:
        client_args["aws_access_key_id"] = access_key
        client_args["aws_secret_access_key"] = secret_key
    if session_token:
        client_args["aws_session_token"] = session_token
    return boto3.client("s3", **client_args)


@st.cache_data(ttl=300, show_spinner=False)
def _load_latest_parquet(bucket: str, prefix: str, region: str) -> tuple[pd.DataFrame, str, datetime]:
    client = _aws_client(region)
    paginator = client.get_paginator("list_objects_v2")
    candidates: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        candidates.extend(
            item
            for item in page.get("Contents", [])
            if item["Key"].lower().endswith(".parquet")
        )
    if not candidates:
        raise FileNotFoundError(
            f"No .parquet objects were found in s3://{bucket}/{prefix}"
        )
    latest = max(candidates, key=lambda item: item["LastModified"])
    response = client.get_object(Bucket=bucket, Key=latest["Key"])
    frame = pd.read_parquet(BytesIO(response["Body"].read()))
    return frame, latest["Key"], latest["LastModified"]


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "Not available"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%d %b %Y, %I:%M %p %Z")


def _label_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    by_normalized = {
        str(column).strip().lower().replace(" ", "_"): str(column)
        for column in frame.columns
    }
    for candidate in candidates:
        if candidate in by_normalized:
            return by_normalized[candidate]
    return None


def _chart(frame: pd.DataFrame, title: str, category_candidates: tuple[str, ...]) -> None:
    if frame.empty:
        st.info(f"No {title.lower()} records are available in this snapshot.")
        return
    category = _label_column(frame, category_candidates)
    numeric = frame.select_dtypes(include="number").columns.tolist()
    numeric = [
        column
        for column in numeric
        if not any(
            token in str(column).lower()
            for token in ("_id", "id_", "number", "code", "latitude", "longitude")
        )
    ]
    if category and numeric:
        preferred_metrics = (
            "passenger",
            "delay",
            "distance",
            "trip",
            "count",
            "volume",
            "frequency",
            "revenue",
        )
        metric = next(
            (
                column
                for candidate in preferred_metrics
                for column in numeric
                if candidate in str(column).lower()
            ),
            numeric[0],
        )
        grouped = (
            frame.groupby(category, dropna=True)[metric]
            .sum()
            .nlargest(10)
            .sort_values()
            .reset_index()
        )
        fig = px.bar(
            grouped,
            x=metric,
            y=category,
            orientation="h",
            title=f"Top {category.replace('_', ' ').title()} by {metric.replace('_', ' ')}",
            color_discrete_sequence=["#087f8c"],
            labels={metric: metric.replace("_", " ").title(), category: ""},
        )
        fig.update_layout(
            height=360,
            margin=dict(l=8, r=16, t=58, b=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_family="DM Sans",
            title_font_family="Space Grotesk",
            showlegend=False,
        )
        fig.update_xaxes(showgrid=True, gridcolor="#edf1f4", zeroline=False)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
    elif category:
        counts = frame[category].value_counts().head(10).sort_values().reset_index()
        counts.columns = [category, "records"]
        fig = px.bar(
            counts,
            x="records",
            y=category,
            orientation="h",
            title=f"Records by {category.replace('_', ' ')}",
            color_discrete_sequence=["#087f8c"],
        )
        fig.update_layout(
            height=360,
            margin=dict(l=8, r=16, t=58, b=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_family="DM Sans",
            title_font_family="Space Grotesk",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            f"{title} data loaded ({len(frame):,} rows), but no recognized label "
            "column is available for a chart. Share your column names to tailor this view."
        )


def _dataset_section(
    frame: pd.DataFrame | None,
    title: str,
    category_candidates: tuple[str, ...],
    object_key: str | None,
) -> None:
    st.subheader(title)
    if frame is None:
        st.warning(f"{title} data has not been loaded.")
        return
    left, right = st.columns([1.15, 1])
    with left:
        _chart(frame, title, category_candidates)
    with right:
        st.markdown("**Latest records**")
        st.dataframe(frame.head(12), use_container_width=True, hide_index=True)
    st.caption(f"`{object_key}` · {len(frame):,} rows · {len(frame.columns)} columns")


with st.sidebar:
    st.markdown("## 🚆 RailPulse")
    st.caption("INDIAN RAILWAYS · GOLD LAYER")
    st.divider()
    st.markdown("### Dashboard")
    st.markdown("Live analytics")
    st.caption("Private S3 · Parquet snapshots")
    refresh = st.button("↻  Refresh data", use_container_width=True)
    if refresh:
        _load_latest_parquet.clear()
        st.rerun()
    st.divider()
    st.caption("Data refreshes automatically every 5 minutes.")
    st.caption("Use the setup guide in README to connect your S3 Gold data.")

st.markdown('<div class="eyebrow">RAILWAY INTELLIGENCE · LIVE DATA</div>', unsafe_allow_html=True)
heading, status = st.columns([4, 1])
with heading:
    st.title("Indian Railways, at a glance")
    st.markdown(
        '<p class="subtle">A clear view of your train and station analytics, powered by the latest Gold snapshots.</p>',
        unsafe_allow_html=True,
    )
with status:
    st.markdown('<br><span class="status-pill">S3 · GOLD LAYER</span>', unsafe_allow_html=True)

bucket = _setting("S3_BUCKET", section="data")
train_prefix = _setting("TRAIN_PREFIX", section="data", default="gold/trains/")
station_prefix = _setting("STATION_PREFIX", section="data", default="gold/stations/")
region = _setting("AWS_DEFAULT_REGION", section="aws") or _setting(
    "region", section="aws", default="ap-south-1"
)

if not bucket:
    st.markdown(
        """
        <div style="background:#fff;border:1px solid #e6edf1;border-radius:16px;padding:24px 28px;margin:18px 0">
          <div class="eyebrow">ACTION REQUIRED</div>
          <h3 style="margin:8px 0">Connect your private S3 Gold data</h3>
          <p style="color:#748494;margin-bottom:0">Add the bucket and read-only AWS credentials to Streamlit secrets.
          The setup guide in <code>README.md</code> shows the exact keys and least-privilege policy. No credentials
          are needed from you in this chat.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

with st.spinner("Connecting to S3 and loading the latest Gold snapshots..."):
    try:
        trains, train_key, train_time = _load_latest_parquet(bucket, train_prefix, region)
        stations, station_key, station_time = _load_latest_parquet(bucket, station_prefix, region)
    except (BotoCoreError, ClientError, FileNotFoundError, OSError, ValueError) as exc:
        st.error("Could not load the configured Gold data from S3.")
        st.code(str(exc))
        st.info(
            "Check the bucket, region, prefixes, IAM permissions, and that each prefix contains "
            "at least one complete Parquet snapshot."
        )
        st.stop()

st.markdown(
    f'<span class="subtle">Last data update: {_format_timestamp(max(train_time, station_time))}</span>',
    unsafe_allow_html=True,
)

train_id_col = _label_column(trains, ("train_number", "train_no", "train_id", "train_name", "name"))
station_id_col = _label_column(
    stations, ("station_code", "station_name", "station_id", "station", "name")
)
metric_cols = st.columns(4)
metric_cols[0].metric("Train records", f"{len(trains):,}")
metric_cols[1].metric(
    "Unique trains",
    f"{trains[train_id_col].nunique():,}" if train_id_col else "—",
)
metric_cols[2].metric("Station records", f"{len(stations):,}")
metric_cols[3].metric(
    "Unique stations",
    f"{stations[station_id_col].nunique():,}" if station_id_col else "—",
)

overview_tab, trains_tab, stations_tab, freshness_tab = st.tabs(
    ["Overview", "Train analytics", "Station analytics", "Data freshness"]
)
with overview_tab:
    st.markdown("")
    left, right = st.columns(2)
    with left:
        _chart(
            trains,
            "Train analytics",
            ("train_name", "train_number", "train_no", "train_id", "name"),
        )
    with right:
        _chart(
            stations,
            "Station analytics",
            ("station_name", "station_code", "station_id", "station", "name"),
        )
    st.caption("Charts use the available category and numeric columns in your Gold snapshots.")

with trains_tab:
    _dataset_section(
        trains,
        "Train analytics",
        ("train_name", "train_number", "train_no", "train_id", "name"),
        train_key,
    )
with stations_tab:
    _dataset_section(
        stations,
        "Station analytics",
        ("station_name", "station_code", "station_id", "station", "name"),
        station_key,
    )
with freshness_tab:
    st.subheader("Gold snapshot health")
    freshness_rows = pd.DataFrame(
        [
            {
                "Dataset": "Trains",
                "Latest object": train_key,
                "Last modified": _format_timestamp(train_time),
                "Rows": f"{len(trains):,}",
                "Columns": len(trains.columns),
            },
            {
                "Dataset": "Stations",
                "Latest object": station_key,
                "Last modified": _format_timestamp(station_time),
                "Rows": f"{len(stations):,}",
                "Columns": len(stations.columns),
            },
        ]
    )
    st.dataframe(freshness_rows, use_container_width=True, hide_index=True)
    st.caption(
        "The dashboard selects the most recently modified .parquet object under each configured prefix. "
        "Publish complete snapshots so a refresh never reads a partially written dataset."
    )
