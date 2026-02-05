import os
import re
import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import pydeck as pdk
from supabase import create_client
from dotenv import load_dotenv
from postgrest.exceptions import APIError

# If you encounter SSL errors, uncomment:
# import ssl
# ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

st.set_page_config(page_title="WiDS Wildfire Timing Dashboard", layout="wide")
st.title("WiDS Wildfire Timing Dashboard")
st.caption("Benchmarks response timing against historical patterns and flags incidents with dangerous delays.")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_KEY. Check your local .env (do not commit it).")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Helpers
# -----------------------------
def to_dt(df: pd.DataFrame, col: str) -> None:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

def coerce_numeric(df: pd.DataFrame, cols) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

def coerce_json_obj(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return None
    return None

@st.cache_data(ttl=300)
def fetch_recent(
    table_name: str,
    columns: str,
    order_col: str,
    max_rows: int,
    page_size: int = 1000,
    order_desc: bool = True,
) -> pd.DataFrame:
    """Fetch recent rows ordered by order_col desc for predictable sampling."""
    all_rows = []
    start = 0
    while start < max_rows:
        end = start + page_size - 1
        resp = (
            supabase.table(table_name)
            .select(columns)
            .order(order_col, desc=order_desc)
            .range(start, end)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size
    return pd.DataFrame(all_rows)

@st.cache_data(ttl=300)
def fetch_where_in(
    table_name: str,
    columns: str,
    in_col: str,
    values,
    chunk: int = 200,
    order_col: str | None = None,
    order_desc: bool = True,
) -> pd.DataFrame:
    """Fetch rows for table_name where in_col IN (values), chunked to avoid timeouts."""
    vals = pd.Series(values).dropna().unique().tolist()
    if not vals:
        return pd.DataFrame()

    out = []
    for i in range(0, len(vals), chunk):
        part = vals[i:i + chunk]
        q = supabase.table(table_name).select(columns).in_(in_col, part)
        if order_col:
            q = q.order(order_col, desc=order_desc)
        resp = q.execute()
        out.extend(resp.data or [])

    return pd.DataFrame(out)

def fetch_evac_zones_for_uids_with_fallback(uids, columns: str, first_chunk: int = 200) -> pd.DataFrame:
    """
    Fetch evac zones for uid_v2 with aggressive chunk fallback on statement timeout.
    This is not cached on purpose because failures should not be cached.
    """
    uids = [u for u in pd.Series(uids).dropna().astype(str).unique().tolist() if u]
    if not uids:
        return pd.DataFrame()

    chunk_sizes = [first_chunk, 100, 50, 25]
    last_err = None

    for chunk in chunk_sizes:
        try:
            rows = []
            for i in range(0, len(uids), chunk):
                part = uids[i:i + chunk]
                resp = (
                    supabase.table("evac_zones_gis_evaczone")
                    .select(columns)
                    .in_("uid_v2", part)
                    .execute()
                )
                rows.extend(resp.data or [])
            return pd.DataFrame(rows)
        except APIError as e:
            last_err = e
            msg = getattr(e, "message", "") or str(e)
            # PostgREST timeout: code 57014
            if "57014" in msg or "statement timeout" in msg:
                continue
            raise

    raise last_err if last_err else RuntimeError("Failed to fetch evac zones (unknown error).")

POINT_RE = re.compile(r"POINT\s*\(\s*([-0-9.]+)\s+([-0-9.]+)\s*\)", re.IGNORECASE)

def parse_point_wkt(s):
    if not isinstance(s, str):
        return None, None
    s2 = s.split(";", 1)[-1].strip()
    m = POINT_RE.search(s2)
    if not m:
        return None, None
    lon = float(m.group(1))
    lat = float(m.group(2))
    return lat, lon

# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("Controls")

max_incident_rows = st.sidebar.slider("Max incident rows to load (recent-first)", 2000, 50000, 15000, step=1000)

analyze_top_n = st.sidebar.slider(
    "Recent wildfires to analyze deeply (affects joins and speed)",
    25, 1500, 300, step=25
)

status_choice = st.sidebar.selectbox(
    "Incident status",
    ["Active only", "All incidents", "Inactive only"],
)

notif_choice = st.sidebar.selectbox("Notification type", ["All", "normal", "silent"])

st.sidebar.divider()
use_signal_keys = st.sidebar.checkbox("Use credible-signal logic from incident changelog", value=True)

SIGNAL_KEYS = [
    "radio_traffic_indicates_structure_threat",
    "radio_traffic_indicates_spotting",
    "radio_traffic_indicates_rate_of_spread",
]

st.sidebar.divider()
st.sidebar.subheader("Timing filters")
max_signal_order = st.sidebar.slider("Max signal → order delay (minutes)", 0, 20000, 2000, step=50)
only_with_signal = st.sidebar.checkbox("Only show incidents with a credible signal", value=False)

# -----------------------------
# Load base incidents (fast)
# -----------------------------
with st.spinner("Loading recent incidents…"):
    ge = fetch_recent(
        "geo_events_geoevent",
        "id,name,geo_event_type,is_active,date_created,date_modified,notification_type,lat,lng",
        order_col="date_created",
        max_rows=max_incident_rows,
        page_size=1000,
        order_desc=True,
    )

to_dt(ge, "date_created")
to_dt(ge, "date_modified")
coerce_numeric(ge, ["lat", "lng"])

# Filter to wildfires for analysis
wf = ge[ge["geo_event_type"] == "wildfire"].copy().rename(columns={"id": "geo_event_id"})

if status_choice == "Active only":
    wf = wf[wf["is_active"] == True]
elif status_choice == "Inactive only":
    wf = wf[wf["is_active"] == False]

if notif_choice != "All":
    wf = wf[wf["notification_type"] == notif_choice]

# Choose the subset for deep joins (recent-first)
wf = wf.sort_values("date_created", ascending=False)
wf_deep = wf.head(analyze_top_n).copy()

# If no wildfires, show maps only and skip everything else
if wf_deep.empty:
    st.warning("No wildfires found in the current incident sample/filters. Increase 'Max incident rows' or change filters.")
    # Still show incident map for whatever is available
    tab_dashboard, tab_explorer = st.tabs(["Dashboard", "Data Explorer"])
    with tab_dashboard:
        st.subheader("Map: wildfire incidents (Active = red, Inactive = white)")
        inc = wf.copy()
        inc = inc.dropna(subset=["lat", "lng"]).copy()
        inc["is_active"] = inc["is_active"].fillna(False)
        inc["fill_color"] = inc["is_active"].apply(lambda x: [255, 0, 0, 200] if x else [255, 255, 255, 170])
        inc["line_color"] = inc["is_active"].apply(lambda x: [255, 0, 0, 255] if x else [120, 120, 120, 255])

        if inc.empty:
            st.info("No wildfire points with valid lat/lng.")
        else:
            layer_inc = pdk.Layer(
                "ScatterplotLayer",
                data=inc.head(8000),
                get_position='[lng, lat]',
                get_radius=2,          # smaller
                radius_units="meters",
                pickable=True,
                filled=True,
                stroked=True,
                get_fill_color="fill_color",
                get_line_color="line_color",
                line_width_min_pixels=1,
            )

            view_state = pdk.ViewState(
                latitude=float(inc["lat"].median()),
                longitude=float(inc["lng"].median()),
                zoom=5,
            )
            tooltip = {"text": "Fire: {name}\nActive: {is_active}\nCreated: {date_created}"}
            st.pydeck_chart(pdk.Deck(layers=[layer_inc], initial_view_state=view_state, tooltip=tooltip), use_container_width=True)
    with tab_explorer:
        st.write("Increase incident rows and adjust filters to load wildfire data.")
    st.stop()

deep_geo_ids = wf_deep["geo_event_id"].dropna().unique().tolist()

# -----------------------------
# Load only the changelog + mapping rows for those incidents (fast enough)
# -----------------------------
with st.spinner("Loading incident changelog and evac mapping for selected wildfires…"):
    ch = fetch_where_in(
        "geo_events_geoeventchangelog",
        "geo_event_id,date_created,changes",
        in_col="geo_event_id",
        values=deep_geo_ids,
        chunk=200,
        order_col="date_created",
        order_desc=True,
    )
    ev_map = fetch_where_in(
        "evac_zone_status_geo_event_map",
        "geo_event_id,uid_v2,date_created",
        in_col="geo_event_id",
        values=deep_geo_ids,
        chunk=200,
        order_col="date_created",
        order_desc=True,
    )

to_dt(ch, "date_created")
to_dt(ev_map, "date_created")
ch["changes_obj"] = ch["changes"].apply(coerce_json_obj) if "changes" in ch.columns else None

# -----------------------------
# Credible signal logic
# -----------------------------
def has_signal(changes_obj) -> bool:
    if not isinstance(changes_obj, dict):
        return False
    return any(k in changes_obj for k in SIGNAL_KEYS)

if use_signal_keys and not ch.empty:
    ch["has_signal"] = ch["changes_obj"].apply(has_signal)
else:
    ch["has_signal"] = False

first_signal = (
    ch[ch["has_signal"]]
    .sort_values("date_created")
    .groupby("geo_event_id", as_index=False)
    .first()[["geo_event_id", "date_created"]]
    .rename(columns={"date_created": "first_signal_time"})
)

# -----------------------------
# Fetch evac zones for the relevant uid_v2 only (can still be heavy, so fallback chunking)
# -----------------------------
ez = pd.DataFrame()
match_rate = 0.0
order_events = pd.DataFrame()

try:
    with st.spinner("Fetching evacuation zones for mapped uid_v2 values…"):
        needed_uids = ev_map["uid_v2"].dropna().astype(str).unique().tolist()
        # Keep columns minimal to reduce payload
        ez_cols = "id,uid_v2,display_name,region_id,is_active,status,external_status,geom_label,source_attribution"
        ez = fetch_evac_zones_for_uids_with_fallback(needed_uids, columns=ez_cols, first_chunk=200)

except APIError as e:
    st.warning(
        "Evac zone fetch timed out. Reduce 'Recent wildfires to analyze deeply' or try again.\n\n"
        f"Error: {str(e)}"
    )
    ez = pd.DataFrame()

# If we got evac zones, join mapping to get evac_zone_id
if not ez.empty and not ev_map.empty:
    ev_map = ev_map.merge(ez[["id", "uid_v2"]], on="uid_v2", how="left").rename(columns={"id": "evac_zone_id"})
    match_rate = 1.0 - ev_map["evac_zone_id"].isna().mean() if len(ev_map) else 0.0

# -----------------------------
# Fetch evac zone changelog only for evac_zone_ids we actually have
# -----------------------------
ez_ch = pd.DataFrame()
first_order = pd.DataFrame({"geo_event_id": pd.Series(dtype="int64"),
                            "order_time": pd.Series(dtype="datetime64[ns, UTC]")})

if "evac_zone_id" in ev_map.columns and ev_map["evac_zone_id"].notna().any():
    evac_zone_ids = ev_map["evac_zone_id"].dropna().astype(int).unique().tolist()

    with st.spinner("Loading evac zone changelog for matched zones…"):
        ez_ch = fetch_where_in(
            "evac_zones_gis_evaczonechangelog",
            "evac_zone_id,date_created,changes",
            in_col="evac_zone_id",
            values=evac_zone_ids,
            chunk=200,
            order_col="date_created",
            order_desc=True,
        )

    to_dt(ez_ch, "date_created")
    ez_ch["changes_obj"] = ez_ch["changes"].apply(coerce_json_obj) if "changes" in ez_ch.columns else None

    def is_order_change(changes_obj) -> bool:
        if not isinstance(changes_obj, dict):
            return False
        for key in ["status", "external_status"]:
            if key in changes_obj:
                v = changes_obj.get(key)
                if isinstance(v, list) and len(v) >= 2:
                    new_val = v[1]
                    if isinstance(new_val, str) and new_val.lower() == "order":
                        return True
        return False

    ez_ch["is_order"] = ez_ch["changes_obj"].apply(is_order_change)

    ez_orders = ez_ch[ez_ch["is_order"]].copy()
    ez_orders = ez_orders.rename(columns={"date_created": "order_time"})[["evac_zone_id", "order_time"]]

    order_events = (
        ev_map.dropna(subset=["evac_zone_id"])
        .merge(ez_orders, on="evac_zone_id", how="inner")
    )

    if not order_events.empty:
        first_order = (
            order_events.sort_values("order_time")
            .groupby("geo_event_id", as_index=False)
            .first()[["geo_event_id", "order_time"]]
        )
        first_order["order_time"] = pd.to_datetime(first_order["order_time"], errors="coerce", utc=True)

# -----------------------------
# Infer dominant region per incident (optional)
# -----------------------------
dominant_region = pd.DataFrame({"geo_event_id": pd.Series(dtype="int64"),
                                "region_id": pd.Series(dtype="float64")})

if not ez.empty and "evac_zone_id" in ev_map.columns and "region_id" in ez.columns:
    ev_map_region = ev_map.merge(
        ez[["id", "region_id"]].rename(columns={"id": "evac_zone_id"}),
        on="evac_zone_id",
        how="left",
    )
    dominant_region = (
        ev_map_region.dropna(subset=["region_id"])
        .groupby(["geo_event_id", "region_id"])
        .size()
        .reset_index(name="n")
        .sort_values(["geo_event_id", "n"], ascending=[True, False])
        .drop_duplicates("geo_event_id")[["geo_event_id", "region_id"]]
    )

# -----------------------------
# Assemble analysis table
# -----------------------------
df = (
    wf_deep.merge(first_signal, on="geo_event_id", how="left")
           .merge(first_order, on="geo_event_id", how="left")
           .merge(dominant_region, on="geo_event_id", how="left")
)

df["first_signal_time"] = pd.to_datetime(df["first_signal_time"], errors="coerce", utc=True)
df["order_time"] = pd.to_datetime(df["order_time"], errors="coerce", utc=True)

df["mins_to_first_signal"] = (df["first_signal_time"] - df["date_created"]).dt.total_seconds() / 60.0
df["mins_signal_to_order"] = (df["order_time"] - df["first_signal_time"]).dt.total_seconds() / 60.0
df["mins_incident_to_order"] = (df["order_time"] - df["date_created"]).dt.total_seconds() / 60.0

df_view = df.copy()
if only_with_signal:
    df_view = df_view[df_view["first_signal_time"].notna()]
df_view = df_view[(df_view["mins_signal_to_order"].isna()) | (df_view["mins_signal_to_order"] <= max_signal_order)]

# -----------------------------
# Tabs
# -----------------------------
tab_dashboard, tab_explorer = st.tabs(["Dashboard", "Data Explorer"])

with tab_dashboard:
    with st.expander("Data health and join checks"):
        st.write(f"Wildfires in deep analysis set: {len(wf_deep):,}")
        st.write(f"Incident changelog rows loaded (filtered): {len(ch):,}")
        st.write(f"Evac map rows loaded (filtered): {len(ev_map):,}")
        st.write(f"Evac zones fetched for mapped uids: {len(ez):,}")
        st.write(f"Evac map → zone match rate (uid_v2 → id): {match_rate:.1%}")
        st.write(f"Evac zone changelog rows loaded (filtered): {len(ez_ch):,}")
        st.write(f"Order events found (after joins): {len(order_events):,}")

    # KPI cards
    c1, c2, c3, c4 = st.columns(4)
    total_incidents = len(df_view)
    with_signal = df_view["first_signal_time"].notna().sum()
    with_order = df_view["order_time"].notna().sum()
    signal_no_order = ((df_view["first_signal_time"].notna()) & (df_view["order_time"].isna())).sum()
    c1.metric("Incidents in view", f"{total_incidents:,}")
    c2.metric("With credible signal", f"{with_signal:,}")
    c3.metric("With evac order", f"{with_order:,}")
    c4.metric("Signal but no order", f"{signal_no_order:,}")

    st.divider()

    # Timing chain panel
    st.subheader("Incident timing chain")
    candidates = df_view.copy().sort_values("date_created", ascending=False)

    if candidates.empty:
        st.info("No incidents available for the current filters.")
    else:
        options = (
            candidates["geo_event_id"].astype(str)
            + " | "
            + candidates["name"].fillna("(no name)")
        ).tolist()
        pick = st.selectbox("Select an incident", options)
        pick_id = int(pick.split("|")[0].strip())
        row = df_view[df_view["geo_event_id"] == pick_id].iloc[0]

        colA, colB, colC, colD = st.columns(4)
        colA.metric("T0 Incident created", str(row["date_created"]))
        colB.metric("T1 First credible signal", str(row["first_signal_time"]) if pd.notna(row["first_signal_time"]) else "None")
        colC.metric("T2 First evac order", str(row["order_time"]) if pd.notna(row["order_time"]) else "None")
        colD.metric("Region (inferred)", str(row["region_id"]) if pd.notna(row["region_id"]) else "Unknown")

        st.write("Signal → Order (mins):", row.get("mins_signal_to_order", np.nan))
        st.write("Incident → Order (mins):", row.get("mins_incident_to_order", np.nan))

    st.divider()

    st.subheader("Wildfire incidents created over time (deep set)")
    tmp = df_view.copy()
    if tmp["date_created"].isna().all():
        st.info("No timestamps available.")
    else:
        tmp["day"] = tmp["date_created"].dt.floor("D")
        counts = tmp.groupby("day", dropna=True).size().reset_index(name="count")
        st.plotly_chart(px.line(counts, x="day", y="count"), use_container_width=True)

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Signal → Order delay distribution (minutes)")
        delays = df_view.dropna(subset=["mins_signal_to_order"])
        if delays.empty:
            st.info("No signal→order delay data available for current filters.")
        else:
            st.plotly_chart(px.histogram(delays, x="mins_signal_to_order", nbins=60), use_container_width=True)

    with right:
        st.subheader("Minutes to first credible signal (distribution)")
        sig = df_view.dropna(subset=["mins_to_first_signal"])
        if sig.empty:
            st.info("No credible-signal timing data available for current filters.")
        else:
            st.plotly_chart(px.histogram(sig, x="mins_to_first_signal", nbins=60), use_container_width=True)

    st.divider()

    st.subheader("Benchmark: signal → order delay vs inferred region history")
    bench = df_view.dropna(subset=["mins_signal_to_order", "region_id"]).copy()
    if bench.empty:
        st.info("Not enough signal→order + region data to benchmark yet.")
    else:
        percentiles = (
            bench.groupby("region_id")["mins_signal_to_order"]
            .quantile([0.5, 0.75, 0.9])
            .unstack()
            .reset_index()
            .rename(columns={0.5: "p50", 0.75: "p75", 0.9: "p90"})
        )
        bench = bench.merge(percentiles, on="region_id", how="left")
        x = bench["mins_signal_to_order"]
        bench["delay_flag"] = np.where(
            x >= bench["p90"], "Danger (≥P90)",
            np.where(x >= bench["p75"], "Slow (P75–P90)", "OK (≤P75)")
        )
        st.plotly_chart(px.histogram(bench, x="mins_signal_to_order", color="delay_flag", nbins=60), use_container_width=True)

    st.divider()

    # Map: incidents colored (active red, inactive white)
    st.subheader("Map: wildfire incidents (Active = red, Inactive = white)")
    inc = wf.copy().dropna(subset=["lat", "lng"]).copy()
    inc["is_active"] = inc["is_active"].fillna(False)
    inc["fill_color"] = inc["is_active"].apply(lambda x: [255, 0, 0, 200] if x else [255, 255, 255, 170])
    inc["line_color"] = inc["is_active"].apply(lambda x: [255, 0, 0, 255] if x else [120, 120, 120, 255])

    if inc.empty:
        st.info("No wildfire points with valid lat/lng for the current filters.")
    else:
        layer_inc = pdk.Layer(
            "ScatterplotLayer",
            data=inc.head(8000),
            get_position='[lng, lat]',
            get_radius=1200,
            radius_units="meters",
            pickable=True,
            filled=True,
            stroked=True,
            get_fill_color="fill_color",
            get_line_color="line_color",
            line_width_min_pixels=1,
        )
        view_state = pdk.ViewState(
            latitude=float(inc["lat"].median()),
            longitude=float(inc["lng"].median()),
            zoom=5,
        )
        tooltip = {"text": "Fire: {name}\nActive: {is_active}\nCreated: {date_created}"}
        st.pydeck_chart(pdk.Deck(layers=[layer_inc], initial_view_state=view_state, tooltip=tooltip), use_container_width=True)

    st.divider()

    # Map: evac zones (if available)
    st.subheader("Map: evacuation zones (label points from geom_label)")
    if ez.empty:
        st.info("Evac zone data not loaded (likely timeout). Reduce 'Recent wildfires to analyze deeply' and reload.")
    else:
        ez_labels = ez.copy()
        ez_labels[["label_lat", "label_lng"]] = ez_labels["geom_label"].apply(lambda x: pd.Series(parse_point_wkt(x)))
        coerce_numeric(ez_labels, ["label_lat", "label_lng"])
        ez_labels = ez_labels.dropna(subset=["label_lat", "label_lng"]).head(8000)

        if ez_labels.empty:
            st.info("No evac zone label points found (geom_label missing or unparsable).")
        else:
            layer_zone = pdk.Layer(
                "ScatterplotLayer",
                data=ez_labels,
                get_position='[label_lng, label_lat]',
                get_radius=900,
                radius_units="meters",
                pickable=True,
                filled=True,
                get_fill_color=[0, 140, 255, 160],
                get_line_color=[0, 0, 0, 255],
                line_width_min_pixels=1,
            )
            view_state2 = pdk.ViewState(
                latitude=float(ez_labels["label_lat"].median()),
                longitude=float(ez_labels["label_lng"].median()),
                zoom=5,
            )
            tooltip2 = {"text": "Zone: {display_name}\nStatus: {status}\nExternal: {external_status}\nRegion: {region_id}\nSource: {source_attribution}"}
            st.pydeck_chart(pdk.Deck(layers=[layer_zone], initial_view_state=view_state2, tooltip=tooltip2), use_container_width=True)

    st.divider()

    st.subheader("Dangerous delay candidates (credible signal present)")
    top_n = st.slider("Show top N candidates", 5, 200, 25)
    danger = df_view[df_view["first_signal_time"].notna()].copy()
    if danger.empty:
        st.info("No incidents with credible signal found for the current filters.")
    else:
        danger["danger_score"] = danger["mins_signal_to_order"].fillna(1e12)
        danger = danger.sort_values("danger_score", ascending=False).head(top_n)
        st.dataframe(
            danger[[
                "geo_event_id", "name", "is_active", "notification_type", "region_id",
                "date_created", "first_signal_time", "order_time", "mins_signal_to_order"
            ]],
            use_container_width=True
        )

with tab_explorer:
    st.title("Data Explorer")
    st.write(
        "This tab shows what was actually loaded for the current run. "
        "The deep analysis set is limited on purpose to prevent Supabase statement timeouts."
    )

    st.subheader("Loaded dataset sizes")
    st.write("geo_events_geoevent (recent):", len(ge))
    st.write("wildfires after filters:", len(wf))
    st.write("wildfires in deep set:", len(wf_deep))
    st.write("geo_events_geoeventchangelog (filtered):", len(ch))
    st.write("evac_zone_status_geo_event_map (filtered):", len(ev_map))
    st.write("evac_zones_gis_evaczone (fetched by uid_v2):", len(ez))
    st.write("evac_zones_gis_evaczonechangelog (filtered):", len(ez_ch))

    st.subheader("Quick peek")
    st.write("Wildfires (deep):")
    st.dataframe(wf_deep.head(200), use_container_width=True)

    st.write("First signal table:")
    st.dataframe(first_signal.head(200), use_container_width=True)

    st.write("First order table:")
    st.dataframe(first_order.head(200), use_container_width=True)

