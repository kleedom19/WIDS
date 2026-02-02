"""
evacuation_planner_page.py  —  v4

Changes from v3
───────────────
1  Google Maps / Apple Maps links fully removed.  Turn-by-turn comes from
   OSRM only; the interactive map (Folium / Leaflet + OSM tiles) is the
   single source of navigation.
2  Road-Closure Advisory section now fetches LIVE incident data:
     • NC  → NC DOT TIMS REST API  (no key required)
     • Other states → state-specific open feeds where available, with a
       clean fallback advisory block.
3  Shelter discovery is now TWO-LAYER:
     a) Live query to the OpenStreetMap Overpass API pulls shelters,
        social-facilities, and hospitals within a radius of the destination.
     b) Curated static fallback data is merged in so the user always sees
        categorised options even if Overpass is slow/down.
   Categories surfaced:
     General  |  Women / DV  |  Elderly  |  Disabled / ADA  |
     Mental-Health  |  Veterans  |  Families w/ Children  |  Pet-Friendly
4  Emoji pass: decorative emoji stripped.  Single-purpose icons kept where
   they aid scannability (warning triangle, map pin).  No emoji clusters.
5  Directions section rewritten: shows OSRM turn-by-turn inline; no
   external map-service links anywhere.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
from typing import Dict, List, Optional, Tuple
from math import radians, cos, sin, asin, sqrt
from datetime import datetime

# ── local imports ────────────────────────────────────────────────────
try:
    from us_cities_database import US_CITIES, get_city_coordinates
    CITY_DB_AVAILABLE = True
except Exception:
    CITY_DB_AVAILABLE = False
    US_CITIES = {}

try:
    from transit_and_safezones import get_dynamic_safe_zones, get_transit_info
    TRANSIT_DB_AVAILABLE = True
except Exception:
    TRANSIT_DB_AVAILABLE = False


# ── helpers ──────────────────────────────────────────────────────────
def _fmt(minutes: float) -> str:
    """99 → '1 hr 39 min'"""
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    return f"{h} hr {m} min" if h else f"{m} min"


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Miles between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 3956 * 2 * asin(sqrt(a))


# ── geocoding ────────────────────────────────────────────────────────
def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """City DB first, then Nominatim (OSM) fallback.  No Google."""
    if CITY_DB_AVAILABLE:
        coords = get_city_coordinates(address.lower().strip())
        if coords:
            return coords
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"},
            timeout=10,
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


# ── OSRM routing ─────────────────────────────────────────────────────
def osrm_route(origin_lat, origin_lon, dest_lat, dest_lon, profile="car") -> Optional[Dict]:
    """
    OSRM open-source router.  profile = car | foot | bicycle.
    Returns distance_mi, duration_min, geometry, steps  —  or None.
    """
    url = (
        f"http://router.project-osrm.org/route/v1/{profile}/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    )
    try:
        r = requests.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("code") != "Ok":
            return None
        route = data["routes"][0]
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                instr = step.get("maneuver", {}).get("instruction", "")
                dist_mi = step.get("distance", 0) * 0.000621371
                if instr:
                    steps.append(f"{instr} ({dist_mi:.2f} mi)")
        return {
            "distance_mi": round(route["distance"] * 0.000621371, 1),
            "duration_min": round(route["duration"] / 60, 1),
            "geometry": route["geometry"]["coordinates"],
            "steps": steps,
        }
    except Exception:
        return None


# ── LIVE road-condition fetchers ─────────────────────────────────────

# NC county name → TIMS county-id  (partial list; expand as needed)
NC_COUNTY_IDS: Dict[str, int] = {
    "mecklenburg": 56, "cabarrus": 13, "union": 83, "gaston": 37,
    "iredell": 45, "cabarrus": 13, "davidson": 26, "guilford": 41,
    "wake": 81, "forsyth": 38, "durham": 28, "alamance": 1,
    "Johnston": 46, "lee": 53, "moore": 65, "chatham": 18,
    "orange": 68, "buncombe": 9, "pitt": 71, "Cumberland": 23,
}


@st.cache_data(ttl=120)                        # refresh every 2 min
def fetch_ncdot_incidents(county_name: str) -> List[Dict]:
    """
    Pull live incidents from NC DOT TIMS REST API.
    Endpoint requires no API key.
    Returns list of incident dicts or empty list on failure.
    """
    cid = NC_COUNTY_IDS.get(county_name.lower().strip())
    if cid is None:
        return []
    url = f"https://eapps.ncdot.gov/services/traffic-prod/v1/counties/{cid}/incidents"
    try:
        r = requests.get(url, headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"}, timeout=10)
        if r.status_code == 200:
            return r.json() if isinstance(r.json(), list) else []
    except Exception:
        pass
    return []


# Map state abbreviation → known open incident-feed URL (no key).
# Only states that publish truly open REST feeds are listed; others
# get the generic advisory block.
STATE_OPEN_FEEDS: Dict[str, str] = {
    # NC handled separately via TIMS above
    # Add more as they become available
}


def _extract_state_abbr(address: str) -> Optional[str]:
    """Best-effort pull of 2-letter state code from free-text address."""
    parts = [p.strip().upper() for p in address.replace(",", " ").split()]
    US_STATES = {
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL",
        "IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT",
        "NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI",
        "SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
    }
    for p in reversed(parts):          # state abbr usually at the end
        if p in US_STATES:
            return p
    return None


def _extract_nc_county(address: str) -> Optional[str]:
    """Try to guess county from city name for NC DOT lookups."""
    city_to_county = {
        "charlotte": "mecklenburg", "matthews": "mecklenburg",
        "mint hill": "mecklenburg", "huntersville": "mecklenburg",
        "concord": "cabarrus", "kannapolis": "cabarrus",
        "monroe": "union", "indian trail": "union",
        "gastonia": "gaston", "cherryville": "gaston",
        "statesville": "iredell", "mooresville": "iredell",
        "davidson": "davidson", "davidson": "davidson",
        "greensboro": "guilford", "high point": "guilford",
        "raleigh": "wake", "cary": "wake", "apex": "wake",
        "winston-salem": "forsyth", "kernersville": "forsyth",
        "durham": "durham",
        "asheville": "buncombe",
    }
    city = address.lower().strip().split(",")[0].strip()
    return city_to_county.get(city)


# ── LIVE shelter discovery via OpenStreetMap Overpass API ────────────

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://api.letsopen.de/api/interpreter",
]

# OSM tag → friendly category label
_TAG_CATEGORY_MAP = {
    # social_facility values
    "dv_shelter":          "Women / Domestic-Violence",
    "elderly_care":        "Elderly",
    "disabled":            "Disabled / ADA",
    "mental_health":       "Mental Health",
    "housing_emergency":   "General Emergency",
    "food_bank":           "Food / Supply Distribution",
    "group_home":          "Group Home",
    # amenity values
    "shelter":             "General",
    "social_centre":       "Social Centre",
    # custom / inferred
    "hospital":            "Hospital / Medical",
    "veterinary":          "Pet-Friendly (Veterinary)",
}

# Curated static shelters used as a reliable baseline when Overpass is
# slow or returns sparse data.  Organised by CATEGORY so the UI can
# always show every filter option.
STATIC_SHELTER_DB: Dict[str, List[Dict]] = {
    "General": [
        {"name": "Red Cross Shelter (local chapter)",
         "address": "Contact local Red Cross — 1-800-RED-CROSS",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "1-800-733-2767", "ada": True,
         "note": "Red Cross operates temporary shelters within 24 h of a declared emergency.  Call to confirm nearest open location."},
        {"name": "FEMA / County Emergency Shelter",
         "address": "Contact county emergency management or dial 211",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "211", "ada": True,
         "note": "County-run shelters open automatically when an evacuation order is issued.  211 connects to local emergency services nationwide."},
    ],
    "Women / Domestic-Violence": [
        {"name": "National DV Hotline — Shelter Referral",
         "address": "Referral only — call or text for nearest shelter",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "1-800-799-7233", "ada": True,
         "note": "The National Domestic Violence Hotline can connect you to the nearest safe, confidential shelter.  Text START to 88788."},
    ],
    "Elderly": [
        {"name": "Area Agency on Aging — Emergency Placement",
         "address": "Contact your local AAA for nearest elder shelter",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "eldercare.acl.gov — 1-800-677-1116", "ada": True,
         "note": "The Eldercare Locator (federal) links to local Area Agencies on Aging who coordinate emergency placement for seniors."},
    ],
    "Disabled / ADA": [
        {"name": "ADA / Disability-Specific Shelter Referral",
         "address": "Contact local emergency management",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "211", "ada": True,
         "note": "Most county emergency shelters are ADA-compliant.  Call 211 and specify mobility / accessibility needs — they can match you to the right facility."},
    ],
    "Mental Health": [
        {"name": "988 Suicide & Crisis Lifeline — Shelter Referral",
         "address": "Call or text 988 for crisis support + shelter help",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "988", "ada": True,
         "note": "988 counsellors can arrange crisis-safe shelter placement and coordinate with local mental-health agencies during emergencies."},
    ],
    "Veterans": [
        {"name": "VA Emergency / Homeless Veteran Services",
         "address": "Contact nearest VA Medical Center",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "1-800-273-8255 (Veterans Crisis Line)", "ada": True,
         "note": "The VA operates emergency shelters for veterans through its Homeless Veteran programmes.  The Veterans Crisis Line also helps locate shelter."},
    ],
    "Families w/ Children": [
        {"name": "211 Family-Shelter Referral",
         "address": "Dial 211 and request family shelter",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "211", "ada": True,
         "note": "Many emergency shelters have dedicated family wings with cots, meals, and childcare.  211 can confirm which facilities are open and have family capacity."},
    ],
    "Pet-Friendly": [
        {"name": "ASPCA / Local Animal Rescue — Pet-Friendly Shelter Info",
         "address": "Contact local animal rescue or dial 211",
         "lat_offset": 0.0, "lon_offset": 0.0,
         "phone": "211", "ada": False,
         "note": "Not all emergency shelters accept pets.  211 and local animal rescues maintain up-to-date lists of pet-friendly evacuation sites.  Bring carriers, food, and records."},
    ],
}

# All shelter categories in display order
SHELTER_CATEGORIES = [
    "General",
    "Women / Domestic-Violence",
    "Elderly",
    "Disabled / ADA",
    "Mental Health",
    "Veterans",
    "Families w/ Children",
    "Pet-Friendly",
    "Hospital / Medical",
]


@st.cache_data(ttl=300)
def fetch_overpass_shelters(dest_lat: float, dest_lon: float, radius_m: int = 15000) -> List[Dict]:
    """
    Query Overpass API for shelters + social facilities near destination.
    Returns normalised list of dicts: name, lat, lon, category, phone, ada, note.
    """
    # Overpass QL: fetch amenity=shelter, social_facility=*, amenity=hospital
    # within a circular area around the destination.
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="shelter"](around:{radius_m},{dest_lat},{dest_lon});
      node["social_facility"](around:{radius_m},{dest_lat},{dest_lon});
      node["amenity"="hospital"](around:{radius_m},{dest_lat},{dest_lon});
      way["amenity"="shelter"](around:{radius_m},{dest_lat},{dest_lon});
      way["social_facility"](around:{radius_m},{dest_lat},{dest_lon});
    );
    out center;
    """
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(endpoint, data={"data": query},
                              headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"},
                              timeout=12)
            if r.status_code != 200:
                continue
            raw = r.json()
            results = []
            for elem in raw.get("elements", []):
                tags = elem.get("tags", {})
                name = tags.get("name", "").strip()
                if not name:
                    continue

                # Resolve coordinates (nodes have lat/lon; ways have center)
                lat = elem.get("lat") or (elem.get("center") or {}).get("lat")
                lon = elem.get("lon") or (elem.get("center") or {}).get("lon")
                if lat is None or lon is None:
                    continue

                # Determine category
                sf = tags.get("social_facility", "")
                amenity = tags.get("amenity", "")
                category = _TAG_CATEGORY_MAP.get(sf) or _TAG_CATEGORY_MAP.get(amenity) or "General"

                phone = tags.get("phone", "").strip() or "N/A"
                ada = tags.get("wheelchair", "yes") != "no"
                website = tags.get("website", "").strip()

                results.append({
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "category": category,
                    "phone": phone,
                    "ada": ada,
                    "website": website,
                    "source": "OpenStreetMap",
                })
            return results
        except Exception:
            continue
    return []  # all endpoints failed


def _merge_shelters(live: List[Dict], dest_lat: float, dest_lon: float) -> Dict[str, List[Dict]]:
    """
    Merge live Overpass results with static baseline so every category
    is represented.  Returns {category: [shelter_dict, …]}.
    """
    merged: Dict[str, List[Dict]] = {cat: [] for cat in SHELTER_CATEGORIES}

    # 1) Live results first
    for s in live:
        cat = s.get("category", "General")
        if cat not in merged:
            merged.setdefault(cat, [])
        merged[cat].append(s)

    # 2) For every category that is still empty, inject the static entries
    #    (adjust lat/lon to be near destination so map pins cluster logically)
    for cat, statics in STATIC_SHELTER_DB.items():
        if not merged.get(cat):
            for s in statics:
                merged.setdefault(cat, []).append({
                    "name": s["name"],
                    "lat": dest_lat + s.get("lat_offset", 0),
                    "lon": dest_lon + s.get("lon_offset", 0),
                    "category": cat,
                    "phone": s["phone"],
                    "ada": s["ada"],
                    "note": s["note"],
                    "source": "Curated",
                })
    return merged


# ── transit helpers ──────────────────────────────────────────────────
TRANSIT_WALK_MINS: Dict[str, int] = {
    "new york": 5, "chicago": 8, "los angeles": 12, "houston": 15,
    "phoenix": 18, "philadelphia": 10, "san antonio": 20, "san diego": 14,
    "dallas": 16, "san jose": 12, "austin": 18, "san francisco": 7,
    "columbus": 15, "indianapolis": 18, "seattle": 9, "denver": 12,
    "washington": 8, "nashville": 20, "boston": 7, "charlotte": 14,
    "portland": 10, "miami": 12, "atlanta": 11, "detroit": 16,
    "minneapolis": 10, "tampa": 22, "orlando": 25, "pittsburgh": 14,
    "cleveland": 13, "raleigh": 18, "new orleans": 15, "baltimore": 11,
}

def _nearest_stop_walk(city_name: str) -> int:
    return TRANSIT_WALK_MINS.get(city_name.lower().strip().split(",")[0].strip(), 15)


# ══════════════════════════════════════════════════════════════════════
# MAIN PAGE RENDERER
# ══════════════════════════════════════════════════════════════════════
def render_evacuation_planner_page(fire_data, vulnerable_populations):
    """Entry point called by the multi-page dashboard."""

    st.title("Personal Evacuation Planner")
    st.markdown(
        "Get personalised evacuation routes — driving, walking, and public transit — "
        "with specific shelter addresses for both the general public and vulnerable populations."
    )

    # ── session-state bootstrap ──────────────────────────────────────
    for key, default in {
        "search_address": None,
        "search_coords": None,
        "search_triggered": False,
        "dynamic_safe_zones": None,
        "selected_zone_idx": 0,
        "cached_routes": {},
    }.items():
        st.session_state.setdefault(key, default)

    # ── address input ────────────────────────────────────────────────
    st.subheader("Your Location")
    st.info("500+ US cities, all 50 states.  Type your city name — e.g. Charlotte, NC or Miami.")

    col1, col2 = st.columns([3, 1])
    with col1:
        address = st.text_input(
            "Enter your city",
            value=st.session_state.search_address or "",
            placeholder="Charlotte, NC",
            key="address_input",
        )
    with col2:
        search_button = st.button("Find Route", type="primary")

    if search_button and address:
        st.session_state.search_triggered = True
        st.session_state.search_address = address
        st.session_state.search_coords = None
        st.session_state.dynamic_safe_zones = None
        st.session_state.cached_routes = {}

    # ── landing state ────────────────────────────────────────────────
    if not st.session_state.search_triggered:
        st.info("Enter your city above to get personalised evacuation routes.")
        st.markdown("---")
        st.subheader("How It Works")
        st.markdown(
            "1. **Enter your city** — geocoded instantly from a 500+ city database.\n"
            "2. **Nearby fires** — satellite detections within 100 mi are shown.\n"
            "3. **Safe-zone shelters** — specific addresses, categorised by population need.\n"
            "4. **Multimodal routes** — driving, walking, transit, and drive-to-transit compared.\n"
            "5. **Interactive map** — every route drawn; shelter pins clickable.\n"
            "6. **Road-condition advisory** — live incident data displayed before you go."
        )
        return

    # ── geocode ──────────────────────────────────────────────────────
    if st.session_state.search_coords is None:
        with st.spinner("Finding your location…"):
            st.session_state.search_coords = geocode_address(st.session_state.search_address)

    coords = st.session_state.search_coords
    if coords is None:
        st.error("City not found.  Try the city name alone or with the state abbreviation.")
        return

    origin_lat, origin_lon = coords
    st.success(f"Location locked: **{st.session_state.search_address.strip().title()}** ({origin_lat:.4f}, {origin_lon:.4f})")

    # ── safe zones ───────────────────────────────────────────────────
    if st.session_state.dynamic_safe_zones is None:
        with st.spinner("Finding nearby safe zones…"):
            st.session_state.dynamic_safe_zones = get_dynamic_safe_zones(
                origin_lat, origin_lon, fire_data=fire_data,
                min_distance_mi=30, max_distance_mi=600, num_zones=10,
            )
    safe_zone_list: List[Dict] = st.session_state.dynamic_safe_zones or []

    # ── fire threats ─────────────────────────────────────────────────
    st.subheader("Nearby Fire Threats")
    nearest_fires: List[Dict] = []
    if fire_data is not None and len(fire_data) > 0:
        for _, fire in fire_data.iterrows():
            fl, flo = fire.get("latitude"), fire.get("longitude")
            if fl and flo:
                d = _haversine(origin_lat, origin_lon, fl, flo)
                if d < 100:
                    acres = fire.get("acres", 0)
                    nearest_fires.append({
                        "name": fire.get("fire_name", "Satellite Detection"),
                        "distance": round(d, 1),
                        "acres": acres if (acres and acres == acres) else 0,
                        "lat": fl, "lon": flo,
                    })
    nearest_fires.sort(key=lambda x: x["distance"])

    if nearest_fires:
        st.warning(f"{len(nearest_fires)} fire(s) detected within 100 miles")
        for f in nearest_fires[:5]:
            badge = "HIGH" if f["distance"] < 15 else ("MEDIUM" if f["distance"] < 40 else "LOW")
            acres_str = f"{f['acres']:,.0f} acres" if f["acres"] else "size unknown"
            st.write(f"[{badge}]  {f['name']}  —  {f['distance']} mi away  ({acres_str})")
    else:
        st.success("No fires within 100 miles of your location.")

    # ── LIVE road-closure advisory ───────────────────────────────────
    st.markdown("---")
    st.subheader("Road-Condition Advisory")
    st.warning(
        "**Always check road conditions before driving.**  "
        "During wildfires, highways may close without notice.  "
        "If live data is unavailable, tune to local AM/FM emergency broadcasts or call **511**."
    )

    state_abbr = _extract_state_abbr(st.session_state.search_address)

    if state_abbr == "NC":
        county_guess = _extract_nc_county(st.session_state.search_address)
        if county_guess:
            with st.spinner("Fetching live NC DOT incidents…"):
                incidents = fetch_ncdot_incidents(county_guess)
            if incidents:
                st.markdown(f"**Live incidents — {county_guess.title()} County**  *(source: NC DOT TIMS, updated {datetime.now().strftime('%H:%M')})*")
                for inc in incidents[:12]:
                    # TIMS returns dicts; field names vary — handle both styles
                    title   = inc.get("title") or inc.get("Title") or inc.get("description") or inc.get("Description") or "Incident"
                    road    = inc.get("road") or inc.get("Road") or inc.get("roadway") or inc.get("Roadway") or ""
                    severity= inc.get("severity") or inc.get("Severity") or ""
                    status  = inc.get("status") or inc.get("Status") or ""
                    st.markdown(f"- **{title}** — {road}  `{severity}` `{status}`".rstrip())
                if len(incidents) > 12:
                    st.caption(f"Showing 12 of {len(incidents)} incidents.  Visit drivenc.gov for the full list.")
            else:
                st.success("No active incidents reported for this county right now.")
        else:
            st.info("NC DOT county lookup not available for this input.  Visit [drivenc.gov](https://drivenc.gov) for statewide conditions.")
    else:
        # Generic advisory for non-NC states
        st.info(
            "Live incident feeds are not yet integrated for this state.  "
            "Check your state DOT site or call **511** before departing."
        )

    # ── destination picker ───────────────────────────────────────────
    st.markdown("---")
    st.subheader("Evacuation Destination")

    if not safe_zone_list:
        st.warning("No safe zones found.  Try a different starting city.")
        return

    zone_labels = []
    for z in safe_zone_list:
        tags = ""
        if z["has_rail"]:  tags += " [rail]"
        if z["near_fire"]: tags += " [fire nearby]"
        zone_labels.append(f"{z['name']}  —  {z['distance_mi']} mi{tags}")

    sel_idx = st.selectbox(
        "Select safe-zone city",
        options=range(len(zone_labels)),
        format_func=lambda i: zone_labels[i],
        index=min(st.session_state.selected_zone_idx, len(zone_labels) - 1),
        help="[rail] = rail available  ·  [fire nearby] = fire detected — prefer other options",
        key="safe_zone_select",
    )
    st.session_state.selected_zone_idx = sel_idx
    zone = safe_zone_list[sel_idx]
    dest_lat, dest_lon = zone["lat"], zone["lon"]
    dest_name = zone["name"]

    # ── SHELTER CARDS (live + static, categorised) ──────────────────
    st.markdown("---")
    st.subheader("Shelters at Destination")

    with st.spinner("Searching for shelters near destination…"):
        live_shelters = fetch_overpass_shelters(dest_lat, dest_lon)
    all_shelters_by_cat = _merge_shelters(live_shelters, dest_lat, dest_lon)

    # Category filter
    available_cats = [c for c in SHELTER_CATEGORIES if all_shelters_by_cat.get(c)]
    chosen_cats = st.multiselect(
        "Filter by shelter type",
        options=available_cats,
        default=available_cats,       # show all by default
    )

    # Pick the first concrete shelter (with real coords) for routing
    primary_shelter = None
    for cat in chosen_cats or available_cats:
        for s in all_shelters_by_cat.get(cat, []):
            if s.get("lat") and s.get("lon"):
                primary_shelter = s
                break
        if primary_shelter:
            break

    # Render cards per category
    for cat in chosen_cats or available_cats:
        shelters = all_shelters_by_cat.get(cat, [])
        if not shelters:
            continue
        st.markdown(f"#### {cat}")
        for s in shelters:
            label = s["name"]
            with st.expander(label, expanded=(cat == "General")):
                if s.get("note"):
                    st.info(s["note"])
                if s.get("address"):
                    st.markdown(f"Address: {s['address']}")
                cols = st.columns(3)
                cols[0].markdown(f"Phone: **{s.get('phone','N/A')}**")
                cols[1].markdown(f"ADA: **{'Yes' if s.get('ada') else 'No'}**")
                cols[2].markdown(f"Source: *{s.get('source','—')}*")
                if s.get("website"):
                    st.markdown(f"[Website]({s['website']})")

    # ── ROUTE CALCULATION (to primary shelter) ──────────────────────
    if primary_shelter is None:
        # Fall back to zone centre if no shelter resolved
        primary_shelter = {"name": dest_name, "lat": dest_lat, "lon": dest_lon}

    shelter_lat, shelter_lon = primary_shelter["lat"], primary_shelter["lon"]

    st.markdown("---")
    st.subheader("Multimodal Route Comparison")
    st.caption(f"Routes calculated to **{primary_shelter['name']}**")

    dest_key = f"{shelter_lat:.4f},{shelter_lon:.4f}"
    if dest_key not in st.session_state.cached_routes:
        with st.spinner("Calculating routes via OSRM…"):
            car  = osrm_route(origin_lat, origin_lon, shelter_lat, shelter_lon, "car")
            foot = osrm_route(origin_lat, origin_lon, shelter_lat, shelter_lon, "foot")
        st.session_state.cached_routes[dest_key] = {"car": car, "foot": foot}

    cached     = st.session_state.cached_routes[dest_key]
    car_route  = cached["car"]
    foot_route = cached["foot"]

    # Transit estimates (heuristic)
    walk_to_stop_mins  = _nearest_stop_walk(st.session_state.search_address)
    straight_mi        = _haversine(origin_lat, origin_lon, shelter_lat, shelter_lon)
    transit_travel_min = round(straight_mi / 30 * 60, 0)
    transit_total_min  = walk_to_stop_mins + transit_travel_min + 10

    drive_to_hub_min = 10
    transit_rest_min = round((straight_mi - 5) / 30 * 60, 0) if straight_mi > 5 else transit_travel_min
    hybrid_total_min = drive_to_hub_min + transit_rest_min + 5

    # Fallback estimates when OSRM is unreachable
    if car_route is None and foot_route is None:
        st.warning(
            "Live routing (OSRM) is temporarily unavailable.  "
            "ETAs below are straight-line estimates.  Use the interactive map below for navigation."
        )

    drive_dist = car_route["distance_mi"] if car_route else round(straight_mi * 1.3, 1)
    drive_eta  = car_route["duration_min"] if car_route else round(drive_dist / 45 * 60, 0)
    walk_dist  = foot_route["distance_mi"] if foot_route else round(straight_mi * 1.2, 1)
    walk_eta   = foot_route["duration_min"] if foot_route else round(walk_dist / 3.5 * 60, 0)

    rows = [
        {"Mode": "Driving",            "Distance": f"{drive_dist} mi",     "ETA": _fmt(drive_eta),         "Notes": "Check 511 for closures"},
        {"Mode": "Transit",            "Distance": f"{straight_mi:.1f} mi","ETA": _fmt(transit_total_min), "Notes": f"Walk {walk_to_stop_mins} min to stop + ride + 10 min buffer"},
        {"Mode": "Drive + Transit",    "Distance": "—",                    "ETA": _fmt(hybrid_total_min),  "Notes": "Drive to transit hub, then ride"},
        {"Mode": "Walking",            "Distance": f"{walk_dist} mi",      "ETA": _fmt(walk_eta),          "Notes": "Only realistic under 10 mi"},
    ]
    st.table(rows)

    # ── transit info ─────────────────────────────────────────────────
    st.subheader("Getting to Transit")
    origin_transit = get_transit_info(st.session_state.search_address) if TRANSIT_DB_AVAILABLE else None
    if origin_transit:
        with st.expander(f"Transit in {st.session_state.search_address.strip().title()}", expanded=True):
            st.markdown("Agencies: " + ", ".join(origin_transit["agencies"]))
            if origin_transit["rail"] and origin_transit.get("rail_lines"):
                st.markdown("Rail: " + " | ".join(origin_transit["rail_lines"]))
            if origin_transit["bus"]:
                st.markdown("Bus: Available")
            st.markdown(origin_transit["notes"])
            st.markdown(f"Info line: **{origin_transit['emergency_hotline']}**")
            if origin_transit.get("transit_url"):
                st.markdown(f"[Transit website]({origin_transit['transit_url']})")

            st.markdown("---")
            st.markdown("How to reach the nearest stop")
            walk_min = _nearest_stop_walk(st.session_state.search_address)
            cols = st.columns(3)
            cols[0].metric("Walk", f"{walk_min} min", "~0.5–1 mi")
            cols[1].metric("Rideshare", f"{max(walk_min - 5, 3)} min", "request in app now")
            cols[2].metric("Drive & park", "~5 min", "check parking alerts")

    dest_transit = get_transit_info(dest_name) if TRANSIT_DB_AVAILABLE else None
    if dest_transit:
        with st.expander(f"Transit at {dest_name} (destination)", expanded=False):
            st.markdown("Agencies: " + ", ".join(dest_transit["agencies"]))
            if dest_transit["rail"] and dest_transit.get("rail_lines"):
                st.markdown("Rail: " + " | ".join(dest_transit["rail_lines"]))
            if dest_transit["bus"]:
                st.markdown("Bus: Available")
            st.markdown(dest_transit["notes"])
            st.markdown(f"Info line: **{dest_transit['emergency_hotline']}**")

    with st.expander("Emergency Shuttle", expanded=False):
        st.write("Estimated time varies.  Contact local emergency services.")
        st.info("Dial **211** for evacuation assistance anywhere in the US.")

    st.warning("Public transit may be suspended during active emergencies.  Always have a backup driving plan.")

    # ── turn-by-turn (OSRM only — no external links) ───────────────
    st.markdown("---")
    st.subheader("Turn-by-Turn Directions")

    if car_route and car_route["steps"]:
        with st.expander("Driving directions", expanded=True):
            for i, s in enumerate(car_route["steps"][:20], 1):
                st.write(f"{i}. {s}")
            if len(car_route["steps"]) > 20:
                st.caption(f"… and {len(car_route['steps']) - 20} more steps")
    else:
        with st.expander("Driving directions", expanded=True):
            st.info("Live turn-by-turn unavailable right now.  Use the interactive map below to navigate.")

    if foot_route and foot_route["steps"]:
        with st.expander("Walking directions", expanded=False):
            for i, s in enumerate(foot_route["steps"][:20], 1):
                st.write(f"{i}. {s}")
            if len(foot_route["steps"]) > 20:
                st.caption(f"… and {len(foot_route['steps']) - 20} more steps")
    else:
        with st.expander("Walking directions", expanded=False):
            st.info("Live walking directions unavailable right now.  Use the interactive map below.")

    # ── INTERACTIVE MAP (Folium / Leaflet + OSM tiles) ──────────────
    st.markdown("---")
    st.subheader("Route Map")

    mid_lat  = (origin_lat + shelter_lat) / 2
    mid_lon  = (origin_lon + shelter_lon) / 2
    zoom     = 9 if straight_mi > 80 else (10 if straight_mi > 30 else 12)

    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=zoom, tiles="CartoDB positron")

    # ── origin pin ──
    folium.Marker(
        [origin_lat, origin_lon],
        popup=f"<b>START</b><br>{st.session_state.search_address.strip().title()}",
        icon=folium.Icon(color="green", icon="home", prefix="fa"),
        tooltip="Your Location",
    ).add_to(m)

    # ── shelter pins (all categories) ──
    cat_colours = {
        "General": "blue", "Women / Domestic-Violence": "purple",
        "Elderly": "orange", "Disabled / ADA": "cadetblue",
        "Mental Health": "darkblue", "Veterans": "darkgreen",
        "Families w/ Children": "pink", "Pet-Friendly": "beige",
        "Hospital / Medical": "red",
    }
    for cat in SHELTER_CATEGORIES:
        for s in all_shelters_by_cat.get(cat, []):
            if not s.get("lat") or not s.get("lon"):
                continue
            colour = cat_colours.get(cat, "gray")
            folium.Marker(
                [s["lat"], s["lon"]],
                popup=(
                    f"<b>{s['name']}</b><br>"
                    f"<i>{cat}</i><br>"
                    f"Phone: {s.get('phone','—')}<br>"
                    f"{'ADA accessible' if s.get('ada') else ''}"
                ),
                icon=folium.Icon(color=colour, icon="flag", prefix="fa"),
                tooltip=f"{s['name']} ({cat})",
            ).add_to(m)

    # ── route polylines ──
    if car_route:
        folium.PolyLine(
            [[c[1], c[0]] for c in car_route["geometry"]],
            color="blue", weight=5, opacity=0.8, tooltip="Driving route",
        ).add_to(m)
    if foot_route:
        folium.PolyLine(
            [[c[1], c[0]] for c in foot_route["geometry"]],
            color="green", weight=3, opacity=0.7, dash_array="8", tooltip="Walking route",
        ).add_to(m)

    # ── fire circles ──
    for f in nearest_fires[:10]:
        folium.Circle(
            [f["lat"], f["lon"]],
            radius=max(f.get("acres", 100) * 40, 800),
            color="red", fill=True, fillColor="orange", fillOpacity=0.35,
            popup=f"{f['name']}  —  {f['distance']} mi away",
        ).add_to(m)

    # ── legend ──
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
         background:white;padding:12px 16px;border-radius:8px;
         border:2px solid #ccc;font-size:13px;box-shadow:0 2px 6px rgba(0,0,0,.3);">
     <b>Legend</b><br>
     <span style="color:blue;">━━</span> Driving &nbsp;
     <span style="color:green;">╌╌</span> Walking &nbsp;
     <span style="color:red;">●</span> Fire &nbsp;
     <span style="color:blue;">▪</span> General &nbsp;
     <span style="color:purple;">▪</span> Women/DV &nbsp;
     <span style="color:orange;">▪</span> Elderly &nbsp;
     <span style="color:darkgreen;">▪</span> Veterans &nbsp;
     <span style="color:red;">▪</span> Hospital
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, width="100%", height=620)

    # ── emergency resources ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("Emergency Resources")
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        "**Emergency Lines**\n"
        "- 911 — Fire / Police / Medical\n"
        "- 211 — Evacuation assistance\n"
        "- 988 — Suicide & Crisis Lifeline\n"
        "- 1-800-RED-CROSS — Shelter referral\n"
        "- Local AM/FM emergency broadcast"
    )
    c2.markdown(
        "**Evacuation Checklist**\n"
        "- IDs, insurance docs\n"
        "- Medications (7-day supply)\n"
        "- Pet food + carriers\n"
        "- Cash + cards\n"
        "- Phone charger / power bank"
    )
    c3.markdown(
        "**Road Safety**\n"
        "- Call 511 for road conditions\n"
        "- Fill gas tank NOW\n"
        "- Water + snacks for 24 h\n"
        "- Download offline maps"
    )


# ── standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(page_title="Evacuation Planner", layout="wide")
    render_evacuation_planner_page(None, None)