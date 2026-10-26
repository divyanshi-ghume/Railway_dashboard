from __future__ import annotations

import os
import re
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
    :root {
      color-scheme: dark;
      --ink: #edf5fb;
      --muted: #9bb0c2;
      --teal: #41dbc6;
      --line: #263b4e;
      --panel: #122436;
      --base: #091521;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp, [data-testid="stAppViewContainer"] { background: var(--base); color: var(--ink); }
    [data-testid="stHeader"] { background: rgba(9, 21, 33, .92); }
    [data-testid="stMain"] { background: radial-gradient(ellipse at 50% -30%, #16334a 0%, var(--base) 62%); }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; color: var(--ink) !important; }
    .block-container { padding-top: 2.1rem; padding-bottom: 3rem; max-width: 1500px; }
    [data-testid="stSidebar"] { background: #0c1c2a; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] * { color: #e5eef6; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #9bb0c2; }
    [data-testid="stMetric"] {
      background: linear-gradient(145deg, #162b3e, #102133);
      border: 1px solid #2a4052;
      border-radius: 16px;
      padding: 18px 20px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, .16);
    }
    [data-testid="stMetricLabel"] { color: #a8bdcc; }
    [data-testid="stMetricValue"] { color: #f4f8fc; font-family: 'Space Grotesk', sans-serif; }
    [data-testid="stMetricDelta"] { color: #41dbc6; }
    div[data-testid="stTabs"] button { color: #a9bdce; font-weight: 600; }
    div[data-testid="stTabs"] button[aria-selected="true"] { color: #41dbc6; }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: #41dbc6; }
    [data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"], label,
    [data-testid="stSelectbox"] *, [data-testid="stSlider"] * { color: #c6d4e0; }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
    }
    [data-testid="stTextInput"] input, [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
      background: #122436;
      border-color: #30475a;
      color: #edf5fb;
    }
    .eyebrow { color: var(--teal); font-size: .76rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
    .subtle { color: #a8bdcc; }
    .status-pill { display: inline-block; padding: 7px 12px; border-radius: 999px; background: #123b3d; color: #75f0d5; font-size: .8rem; font-weight: 700; border: 1px solid #23605d; }
    .section-card { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; }
    div.stButton > button, div.stDownloadButton > button {
      border: 1px solid #365265;
      border-radius: 10px;
      background: #14293b;
      color: #e9f3fa;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
      border-color: #41dbc6;
      color: #41dbc6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _setting(name: str, *, section: str | None = None, default: str = "") -> str:
    aliases = {
        "AWS_DEFAULT_REGION": ("AWS_DEFAULT_REGION", "AWS_REGION", "region"),
        "AWS_ACCESS_KEY_ID": ("AWS_ACCESS_KEY_ID", "access_key_id"),
        "AWS_SECRET_ACCESS_KEY": ("AWS_SECRET_ACCESS_KEY", "secret_access_key"),
        "AWS_SESSION_TOKEN": ("AWS_SESSION_TOKEN", "session_token"),
        "S3_BUCKET": ("S3_BUCKET", "S3_BUCKET_NAME"),
        "S3_GOLD_PREFIX": ("S3_GOLD_PREFIX",),
        "TRAIN_PREFIX": ("TRAIN_PREFIX",),
        "STATION_PREFIX": ("STATION_PREFIX",),
    }
    names = aliases.get(name, (name,))
    for candidate in names:
        env_value = os.getenv(candidate)
        if env_value:
            return env_value
    try:
        secrets: Any = st.secrets
        for candidate in names:
            if section:
                value = secrets.get(section, {}).get(candidate)
                if value:
                    return str(value)
            value = secrets.get(candidate)
            if value:
                return str(value)
        return default
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
def _load_latest_parquet(
    bucket: str,
    prefix: str,
    region: str,
    dataset_hint: str = "",
) -> tuple[pd.DataFrame, str, datetime]:
    client = _aws_client(region)
    paginator = client.get_paginator("list_objects_v2")
    candidates: list[dict[str, Any]] = []
    dataset_pattern = None
    if dataset_hint:
        terms = (
            ("train", "trains")
            if dataset_hint == "train"
            else ("station", "stations")
        )
        dataset_pattern = re.compile(
            r"(?:^|[^a-z])(?:" + "|".join(terms) + r")(?:[^a-z]|$)",
            re.IGNORECASE,
        )
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        candidates.extend(
            item
            for item in page.get("Contents", [])
            if item["Key"].lower().endswith(".parquet")
            and (
                dataset_pattern is None
                or dataset_pattern.search(item["Key"].replace("/", "_"))
            )
        )
    if not candidates:
        detail = (
            f" with a '{dataset_hint}' directory or filename"
            if dataset_hint
            else ""
        )
        raise FileNotFoundError(
            f"No .parquet objects{detail} were found in s3://{bucket}/{prefix}"
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


def _metric_columns(frame: pd.DataFrame) -> list[str]:
    return [
        str(column)
        for column in frame.select_dtypes(include="number").columns
        if not any(
            token in str(column).lower()
            for token in ("_id", "id_", "number", "code", "latitude", "longitude")
        )
    ]


def _humanize(column: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", column)).strip().title()


def _metric_label(column: str) -> str:
    return re.sub(
        r"^(?:avg|average|mean)\s+",
        "",
        _humanize(column),
        flags=re.IGNORECASE,
    )


def _value_for_metric(frame: pd.DataFrame, terms: tuple[str, ...]) -> tuple[str, float] | None:
    matches = [
        column
        for column in _metric_columns(frame)
        if any(term in str(column).lower() for term in terms)
    ]
    if not matches:
        return None
    column = matches[0]
    value = frame[column].mean()
    if pd.isna(value):
        return None
    return column, float(value)


def _chart(
    frame: pd.DataFrame,
    title: str,
    category_candidates: tuple[str, ...],
    chart_key: str,
) -> None:
    if frame.empty:
        st.info(f"No {title.lower()} records are available in this snapshot.")
        return
    category = _label_column(frame, category_candidates)
    numeric = _metric_columns(frame)
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
            .mean()
            .nlargest(10)
            .sort_values()
            .reset_index()
        )
        fig = px.bar(
            grouped,
            x=metric,
            y=category,
            orientation="h",
            title=f"Average {_metric_label(metric)} by {category.replace('_', ' ').title()}",
            color_discrete_sequence=["#41dbc6"],
            labels={metric: _metric_label(metric), category: ""},
        )
        fig.update_layout(
            height=360,
            margin=dict(l=8, r=16, t=58, b=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_family="DM Sans",
            font_color="#d9e6f0",
            title_font_family="Space Grotesk",
            title_font_color="#edf5fb",
            showlegend=False,
        )
        fig.update_xaxes(showgrid=True, gridcolor="#263b4e", zeroline=False, tickfont_color="#a9bdce", title_font_color="#a9bdce")
        fig.update_yaxes(showgrid=False, tickfont_color="#d5e1eb", title_font_color="#a9bdce")
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
    elif category:
        counts = frame[category].value_counts().head(10).sort_values().reset_index()
        counts.columns = [category, "records"]
        fig = px.bar(
            counts,
            x="records",
            y=category,
            orientation="h",
            title=f"Records by {category.replace('_', ' ')}",
            color_discrete_sequence=["#41dbc6"],
        )
        fig.update_layout(
            height=360,
            margin=dict(l=8, r=16, t=58, b=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_family="DM Sans",
            font_color="#d9e6f0",
            title_font_family="Space Grotesk",
            title_font_color="#edf5fb",
            showlegend=False,
        )
        fig.update_xaxes(showgrid=True, gridcolor="#263b4e", tickfont_color="#a9bdce")
        fig.update_yaxes(showgrid=False, tickfont_color="#d5e1eb")
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
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
    chart_key: str,
) -> None:
    st.subheader(title)
    if frame is None:
        st.warning(f"{title} data has not been loaded.")
        return
    numeric_columns = _metric_columns(frame)
    filtered = frame.copy()
    filterable = [
        str(column)
        for column in frame.select_dtypes(exclude="number").columns
        if 1 < frame[column].nunique(dropna=True) <= 100
    ]
    st.markdown("#### Explore this Gold dataset")
    controls = st.columns([1.25, 1.25, 1, 1])
    with controls[0]:
        metric = (
            st.selectbox(
                "Performance metric",
                numeric_columns,
                format_func=_metric_label,
                key=f"{chart_key}-metric",
            )
            if numeric_columns
            else None
        )
    with controls[1]:
        category = (
            st.selectbox(
                "Group by",
                filterable,
                format_func=_humanize,
                key=f"{chart_key}-category",
            )
            if filterable
            else None
        )
    with controls[2]:
        top_n = st.selectbox(
            "Show top",
            [5, 10, 15, 20],
            index=1,
            key=f"{chart_key}-top-n",
        )
    with controls[3]:
        filter_column = (
            st.selectbox(
                "Filter by",
                ["All"] + filterable,
                format_func=lambda value: "No filter" if value == "All" else _humanize(value),
                key=f"{chart_key}-filter-column",
            )
            if filterable
            else "All"
        )
    if filter_column and filter_column != "All":
        options = sorted(frame[filter_column].dropna().unique().tolist(), key=str)
        selected = st.multiselect(
            f"Select {_humanize(filter_column)} values",
            options,
            format_func=str,
            key=f"{chart_key}-filter-values",
        )
        if selected:
            filtered = filtered[filtered[filter_column].isin(selected)]
    left, right = st.columns([1.15, 1])
    if metric and category:
        grouped = (
            filtered.groupby(category, dropna=True)[metric]
            .mean()
            .nlargest(top_n)
            .sort_values()
            .reset_index()
        )
        with left:
            if grouped.empty:
                st.info("No rows match the selected filters.")
            else:
                fig = px.bar(
                    grouped,
                    x=metric,
                    y=category,
                    orientation="h",
                    title=f"Average {_metric_label(metric)} by {_humanize(category)}",
                    color=metric,
                    color_continuous_scale=["#155e75", "#41dbc6", "#ffc56e"],
                    labels={metric: _metric_label(metric), category: ""},
                )
                fig.update_layout(
                    height=390,
                    margin=dict(l=8, r=16, t=60, b=12),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_family="DM Sans",
                    font_color="#d9e6f0",
                    title_font_family="Space Grotesk",
                    title_font_color="#edf5fb",
                    coloraxis_showscale=False,
                )
                fig.update_xaxes(showgrid=True, gridcolor="#263b4e", tickfont_color="#a9bdce")
                fig.update_yaxes(showgrid=False, tickfont_color="#d5e1eb")
                st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}-ranking")
        with right:
            if len(filtered) > 1:
                fig = px.histogram(
                    filtered,
                    x=metric,
                    nbins=24,
                    title=f"{_metric_label(metric)} distribution",
                    color_discrete_sequence=["#41dbc6"],
                    labels={metric: _metric_label(metric)},
                )
                fig.update_layout(
                    height=390,
                    margin=dict(l=8, r=16, t=60, b=12),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_family="DM Sans",
                    font_color="#d9e6f0",
                    title_font_family="Space Grotesk",
                    title_font_color="#edf5fb",
                )
                fig.update_xaxes(showgrid=False, tickfont_color="#a9bdce")
                fig.update_yaxes(showgrid=True, gridcolor="#263b4e", tickfont_color="#a9bdce")
                st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}-distribution")
    elif metric:
        st.info("No suitable category field was found; showing the available metric and records instead.")
    st.markdown(f"#### Records · {len(filtered):,} shown")
    st.dataframe(filtered.head(100), use_container_width=True, hide_index=True)
    st.download_button(
        f"Download filtered {_humanize(title)} CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"{title.lower().replace(' ', '_')}_gold.csv",
        mime="text/csv",
        key=f"{chart_key}-download",
    )
    st.caption(f"`{object_key}` · {len(filtered):,} of {len(frame):,} rows · {len(frame.columns)} columns")


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
gold_prefix = _setting("S3_GOLD_PREFIX", section="data")
train_prefix = _setting("TRAIN_PREFIX", section="data")
station_prefix = _setting("STATION_PREFIX", section="data")
train_hint = ""
station_hint = ""
if gold_prefix:
    gold_prefix = gold_prefix.strip("/") + "/"
    if not train_prefix:
        train_prefix = gold_prefix
        train_hint = "train"
    if not station_prefix:
        station_prefix = gold_prefix
        station_hint = "station"
train_prefix = train_prefix or "gold/trains/"
station_prefix = station_prefix or "gold/stations/"
region = _setting("AWS_DEFAULT_REGION", section="aws") or _setting(
    "region", section="aws", default="ap-south-1"
)

if not bucket:
    st.markdown(
        """
        <div style="background:#122436;border:1px solid #263b4e;border-radius:16px;padding:24px 28px;margin:18px 0">
          <div class="eyebrow">ACTION REQUIRED</div>
          <h3 style="margin:8px 0">Connect your private S3 Gold data</h3>
          <p style="color:#a8bdcc;margin-bottom:0">Add the bucket and read-only AWS credentials to Streamlit secrets.
          The setup guide in <code>README.md</code> shows the exact keys and least-privilege policy. No credentials
          are needed from you in this chat.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

with st.spinner("Connecting to S3 and loading the latest Gold snapshots..."):
    try:
        trains, train_key, train_time = _load_latest_parquet(
            bucket, train_prefix, region, train_hint
        )
        stations, station_key, station_time = _load_latest_parquet(
            bucket, station_prefix, region, station_hint
        )
    except (BotoCoreError, ClientError, FileNotFoundError, OSError, ValueError) as exc:
        st.error("Could not load the configured Gold data from S3.")
        st.code(str(exc))
        st.info(
            "Check the bucket, region, prefixes, IAM permissions, and that each prefix contains "
            "at least one complete Parquet snapshot. With S3_GOLD_PREFIX, filenames or folders "
            "must identify train and station data; otherwise set TRAIN_PREFIX and STATION_PREFIX separately."
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
train_delay = _value_for_metric(trains, ("delay", "late"))
station_passengers = _value_for_metric(stations, ("passenger", "ridership"))
train_distance = _value_for_metric(trains, ("distance", "km"))
station_trains = _value_for_metric(stations, ("train_count", "train_frequency", "trains"))
extra_metrics = st.columns(4)
extra_metrics[0].metric(
    f"Avg {_metric_label(train_delay[0])}" if train_delay else "Train delay",
    f"{train_delay[1]:,.1f}" if train_delay else "No metric",
)
extra_metrics[1].metric(
    f"Avg {_metric_label(train_distance[0])}" if train_distance else "Train distance",
    f"{train_distance[1]:,.1f}" if train_distance else "No metric",
)
extra_metrics[2].metric(
    f"Avg {_metric_label(station_passengers[0])}" if station_passengers else "Station passengers",
    f"{station_passengers[1]:,.1f}" if station_passengers else "No metric",
)
extra_metrics[3].metric(
    f"Avg {_metric_label(station_trains[0])}" if station_trains else "Trains per station",
    f"{station_trains[1]:,.1f}" if station_trains else "No metric",
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
            "train-overview",
        )
    with right:
        _chart(
            stations,
            "Station analytics",
            ("station_name", "station_code", "station_id", "station", "name"),
            "station-overview",
        )
    st.caption("Charts use the available category and numeric columns in your Gold snapshots.")

with trains_tab:
    _dataset_section(
        trains,
        "Train analytics",
        ("train_name", "train_number", "train_no", "train_id", "name"),
        train_key,
        "train-details",
    )
with stations_tab:
    _dataset_section(
        stations,
        "Station analytics",
        ("station_name", "station_code", "station_id", "station", "name"),
        station_key,
        "station-details",
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
    quality_rows = []
    for dataset_name, dataset in (("Trains", trains), ("Stations", stations)):
        missing_count = int(dataset.isna().sum().sum())
        total_cells = int(dataset.shape[0] * dataset.shape[1])
        quality_rows.append(
            {
                "Dataset": dataset_name,
                "Rows": len(dataset),
                "Columns": len(dataset.columns),
                "Missing values": missing_count,
                "Missing cells": f"{missing_count / total_cells:.1%}" if total_cells else "0.0%",
                "Duplicate rows": int(dataset.duplicated().sum()),
                "Numeric metrics": len(_metric_columns(dataset)),
            }
        )
    st.markdown("#### Gold data quality")
    st.dataframe(pd.DataFrame(quality_rows), use_container_width=True, hide_index=True)
    st.caption(
        "The dashboard selects the most recently modified .parquet object under each configured prefix. "
        "Publish complete snapshots so a refresh never reads a partially written dataset. "
        "Quality checks are computed from the loaded snapshots."
    )
