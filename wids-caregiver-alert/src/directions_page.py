"""
directions_page.py  —  v1

Standalone "Directions & Navigation" page for the WiDS Caregiver Alert app.

What this page does
───────────────────
Google-Maps-style point-A-to-point-B directions with four transport modes:

  1. Driving        – OSRM car profile  (turn-by-turn + polyline)
  2. Walking        – OSRM foot profile (turn-by-turn + polyline)
  3. Public Transit – heuristic stop-finder via Overpass + walk-ride-walk
                      itinerary with real transit-stop pins on map
  4. Combined       – drive-to-nearest-transit-hub, then ride, then short walk

Integrated layers on the interactive map
─────────────────────────────────────────
  • Route polylines colour-coded per mode (active = bold, others = faint)
  • Fire-danger circles (from live MODIS/VIIRS data passed in by the dashboard)
  • Road-closure advisory pins (NC DOT TIMS / Caltrans / WSDOT / OSM nationwide)
  • Transit-stop pins pulled live from OpenStreetMap Overpass
  • OSM road-layer overlay for visual traffic context

Free / open APIs used  (no paid key required for core routing)
───────────────────────────────────────────────────────────────
  • Nominatim        – geocoding          (OSM, no key)
  • OSRM            – car / foot routing  (project-osrm.org, no key)
  • Overpass        – transit stops       (overpass-api.de, no key)
  • NC DOT TIMS     – road incidents (NC)   (eapps.ncdot.gov, no key)
  • Caltrans        – emergency closures (CA) (gis.dot.ca.gov ArcGIS, no key)
  • WSDOT           – traveler incidents (WA) (wsdot.wa.gov, no key)
  • Overpass        – construction/closure tags (all states fallback, no key)
  • Leaflet / OSM   – base map + road overlay (no key)
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from typing import Dict, List, Optional, Tuple
from math import radians, cos, sin, asin, sqrt
from datetime import datetime


# ── local imports ────────────────────────────────────────────────────
try:
    from us_cities_database import get_city_coordinates
    CITY_DB_AVAILABLE = True
except Exception:
    CITY_DB_AVAILABLE = False

try:
    from transit_and_safezones import get_transit_info
    TRANSIT_DB_AVAILABLE = True
except Exception:
    TRANSIT_DB_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════

OSRM_BASE = "http://router.project-osrm.org/route/v1"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://api.letsopen.de/api/interpreter",
]

NC_COUNTY_IDS: Dict[str, int] = {
    "mecklenburg": 56, "cabarrus": 13, "union": 83, "gaston": 37,
    "iredell": 45, "davidson": 26, "guilford": 41, "wake": 81,
    "forsyth": 38, "durham": 28, "alamance": 1, "johnston": 46,
    "lee": 53, "moore": 65, "chatham": 18, "orange": 68,
    "buncombe": 9, "pitt": 71, "cumberland": 23,
}

CITY_TO_NC_COUNTY = {
    "charlotte": "mecklenburg", "matthews": "mecklenburg",
    "mint hill": "mecklenburg", "huntersville": "mecklenburg",
    "concord": "cabarrus", "kannapolis": "cabarrus",
    "monroe": "union", "indian trail": "union",
    "gastonia": "gaston", "statesville": "iredell",
    "mooresville": "iredell", "davidson": "davidson",
    "greensboro": "guilford", "high point": "guilford",
    "raleigh": "wake", "cary": "wake", "apex": "wake",
    "winston-salem": "forsyth", "kernersville": "forsyth",
    "durham": "durham", "asheville": "buncombe",
}

# ── 50-state + DC DOT / 511 fallback links ──────────────────────────
STATE_DOT_LINKS: Dict[str, Dict[str, str]] = {
    "AL":{"name":"Alabama",         "url":"https://www.aldot.gov/"},
    "AK":{"name":"Alaska",          "url":"https://www.dot.alaska.gov/"},
    "AZ":{"name":"Arizona",         "url":"https://adot.gov/"},
    "AR":{"name":"Arkansas",        "url":"https://www.ardot.gov/"},
    "CA":{"name":"California",      "url":"https://roads.dot.ca.gov/"},
    "CO":{"name":"Colorado",        "url":"https://cotrip.org/"},
    "CT":{"name":"Connecticut",     "url":"https://www.dot.ct.gov/"},
    "DE":{"name":"Delaware",        "url":"https://www.deldot.gov/"},
    "DC":{"name":"D.C.",            "url":"https://ddot.dc.gov/"},
    "FL":{"name":"Florida",         "url":"https://www.fdot.gov/"},
    "GA":{"name":"Georgia",         "url":"https://www.ga511.com/"},
    "HI":{"name":"Hawaii",          "url":"https://www.hawaii.gov/dot/"},
    "ID":{"name":"Idaho",           "url":"https://www.itd.idaho.gov/"},
    "IL":{"name":"Illinois",        "url":"https://www.getaroundillinois.com/"},
    "IN":{"name":"Indiana",         "url":"https://www.in.gov/dot/"},
    "IA":{"name":"Iowa",            "url":"https://www.traveler.iowa.gov/"},
    "KS":{"name":"Kansas",          "url":"https://www.kdot.kansas.gov/"},
    "KY":{"name":"Kentucky",        "url":"https://511.ky.gov/"},
    "LA":{"name":"Louisiana",       "url":"https://www.louisianabelieves.com/"},
    "ME":{"name":"Maine",           "url":"https://www.maine.gov/dot/"},
    "MD":{"name":"Maryland",        "url":"https://www.sha.maryland.gov/"},
    "MA":{"name":"Massachusetts",   "url":"https://www.mass.gov/orgs/massachusetts-department-of-transportation"},
    "MI":{"name":"Michigan",        "url":"https://www.michigan.gov/mdot/"},
    "MN":{"name":"Minnesota",       "url":"https://511.mn.gov/"},
    "MS":{"name":"Mississippi",     "url":"https://www.mdot.ms.gov/"},
    "MO":{"name":"Missouri",        "url":"https://www.modot.mo.gov/"},
    "MT":{"name":"Montana",         "url":"https://www.montana.gov/dot/"},
    "NE":{"name":"Nebraska",        "url":"https://www.nebraska.gov/dot/"},
    "NV":{"name":"Nevada",          "url":"https://www.nevadadot.com/"},
    "NH":{"name":"New Hampshire",   "url":"https://www.nhdot.nh.gov/"},
    "NJ":{"name":"New Jersey",      "url":"https://www.nj511.org/"},
    "NM":{"name":"New Mexico",      "url":"https://www.nmtd.nm.gov/"},
    "NY":{"name":"New York",        "url":"https://www.dot.ny.gov/"},
    "NC":{"name":"North Carolina",  "url":"https://www.ncdot.gov/"},
    "ND":{"name":"North Dakota",    "url":"https://www.dot.nd.gov/"},
    "OH":{"name":"Ohio",            "url":"https://www.ohio511.com/"},
    "OK":{"name":"Oklahoma",        "url":"https://www.odot.ok.gov/"},
    "OR":{"name":"Oregon",          "url":"https://www.oregon511.org/"},
    "PA":{"name":"Pennsylvania",    "url":"https://www.penndot.pa.gov/"},
    "RI":{"name":"Rhode Island",    "url":"https://www.ridot.ri.gov/"},
    "SC":{"name":"South Carolina",  "url":"https://www.scdot.org/"},
    "SD":{"name":"South Dakota",    "url":"https://www.sdtransporation.sd.gov/"},
    "TN":{"name":"Tennessee",       "url":"https://www.tn.gov/tdot/"},
    "TX":{"name":"Texas",           "url":"https://www.txdot.gov/"},
    "UT":{"name":"Utah",            "url":"https://www.udot.utah.gov/"},
    "VT":{"name":"Vermont",         "url":"https://www.vtrans.vermont.gov/"},
    "VA":{"name":"Virginia",        "url":"https://www.vdot.virginia.gov/"},
    "WA":{"name":"Washington",      "url":"https://www.wsdot.wa.gov/"},
    "WV":{"name":"West Virginia",   "url":"https://www.wvdot.com/"},
    "WI":{"name":"Wisconsin",       "url":"https://www.dot.wisconsin.gov/"},
    "WY":{"name":"Wyoming",         "url":"https://www.wyoming.gov/dot/"},
}

# ── Major intercity-bus terminals (Greyhound / FlixBus / Megabus) ────
# Static seed so the page always has intercity options even if Overpass
# returns nothing.  Each entry: (city_display, lat, lon, carriers, address)
INTERCITY_TERMINALS: List[Dict] = [
    # Southeast
    {"city":"Charlotte, NC",        "lat":35.2272, "lon":-80.8431, "carriers":["Greyhound","FlixBus"],        "address":"601 E Trade St"},
    {"city":"Raleigh, NC",          "lat":35.7721, "lon":-78.6386, "carriers":["Greyhound","FlixBus"],        "address":"316 W Jones St"},
    {"city":"Atlanta, GA",          "lat":33.7490, "lon":-84.3880, "carriers":["Greyhound","FlixBus"],        "address":"227 Peachtree St NE"},
    {"city":"Miami, FL",            "lat":25.7617, "lon":-80.1918, "carriers":["Greyhound","FlixBus"],        "address":"3801 NW 7th St"},
    {"city":"Orlando, FL",          "lat":28.5383, "lon":-81.3792, "carriers":["Greyhound","FlixBus"],        "address":"1717 S Orange Blossom Trail"},
    {"city":"Nashville, TN",        "lat":36.1627, "lon":-86.7816, "carriers":["Greyhound","FlixBus"],        "address":"200 S 11th Ave"},
    {"city":"New Orleans, LA",      "lat":29.9511, "lon":-90.0715, "carriers":["Greyhound","FlixBus"],        "address":"1522 Tulane Ave"},
    {"city":"Birmingham, AL",       "lat":33.5206, "lon":-86.8024, "carriers":["Greyhound"],                  "address":"2100 11th Ave N"},
    # Northeast
    {"city":"New York, NY",         "lat":40.7580, "lon":-73.9855, "carriers":["Greyhound","FlixBus","Megabus"], "address":"Port Authority Bus Terminal, 42nd St"},
    {"city":"Washington, DC",       "lat":38.8951, "lon":-77.0369, "carriers":["Greyhound","FlixBus","Megabus"], "address":"1200 1st Ave NE"},
    {"city":"Philadelphia, PA",     "lat":39.9526, "lon":-75.1652, "carriers":["Greyhound","FlixBus","Megabus"], "address":"1100 Market St"},
    {"city":"Boston, MA",           "lat":42.3601, "lon":-71.0589, "carriers":["Greyhound","FlixBus","Megabus"], "address":"South Station"},
    {"city":"Baltimore, MD",        "lat":39.2904, "lon":-76.6122, "carriers":["Greyhound","FlixBus"],        "address":"2400 W Baltimore St"},
    {"city":"Pittsburgh, PA",       "lat":40.4406, "lon":-79.9959, "carriers":["Greyhound","FlixBus"],        "address":"2702 Liberty Ave"},
    # Midwest
    {"city":"Chicago, IL",          "lat":41.8781, "lon":-87.6298, "carriers":["Greyhound","FlixBus","Megabus"], "address":"141 W Jackson Blvd"},
    {"city":"Detroit, MI",          "lat":42.3314, "lon":-83.0458, "carriers":["Greyhound","FlixBus"],        "address":"1200 Howard St"},
    {"city":"Cleveland, OH",        "lat":41.4993, "lon":-81.6944, "carriers":["Greyhound","FlixBus"],        "address":"2828 Ontario St"},
    {"city":"Indianapolis, IN",     "lat":39.7684, "lon":-86.1581, "carriers":["Greyhound","FlixBus"],        "address":"350 E Washington St"},
    {"city":"Minneapolis, MN",      "lat":44.9778, "lon":-93.2650, "carriers":["Greyhound","FlixBus"],        "address":"24 E Hennepin Ave"},
    {"city":"St. Louis, MO",        "lat":38.6270, "lon":-90.1994, "carriers":["Greyhound","FlixBus"],        "address":"892 St. Ferdinand St"},
    {"city":"Milwaukee, WI",        "lat":43.0389, "lon":-87.9065, "carriers":["Greyhound","FlixBus"],        "address":"105 N 6th St"},
    # South / Southwest
    {"city":"Dallas, TX",           "lat":32.7767, "lon":-96.7970, "carriers":["Greyhound","FlixBus"],        "address":"8525 Stemmons Fwy"},
    {"city":"Houston, TX",          "lat":29.7604, "lon":-95.3698, "carriers":["Greyhound","FlixBus"],        "address":"2041 Polk St"},
    {"city":"San Antonio, TX",      "lat":29.4241, "lon":-98.4936, "carriers":["Greyhound","FlixBus"],        "address":"127 Concepcion St"},
    {"city":"Austin, TX",           "lat":30.2672, "lon":-97.7431, "carriers":["Greyhound","FlixBus"],        "address":"916 W 6th St"},
    {"city":"Phoenix, AZ",          "lat":33.4484, "lon":-112.0740,"carriers":["Greyhound","FlixBus"],        "address":"2121 W Indian School Rd"},
    {"city":"Albuquerque, NM",      "lat":35.0844, "lon":-106.6504,"carriers":["Greyhound"],                  "address":"201 E Tijeras Ave"},
    {"city":"Oklahoma City, OK",    "lat":35.4676, "lon":-97.5164, "carriers":["Greyhound","FlixBus"],        "address":"712 SW 8th St"},
    # West
    {"city":"Los Angeles, CA",      "lat":34.0522, "lon":-118.2437,"carriers":["Greyhound","FlixBus","Megabus"], "address":"1716 E 7th St"},
    {"city":"San Francisco, CA",    "lat":37.7749, "lon":-122.4194,"carriers":["Greyhound","FlixBus","Megabus"], "address":"200 Folsom St"},
    {"city":"San Diego, CA",        "lat":32.7157, "lon":-117.1611,"carriers":["Greyhound","FlixBus"],        "address":"120 W Broadway"},
    {"city":"Sacramento, CA",       "lat":38.5816, "lon":-121.4944,"carriers":["Greyhound","FlixBus"],        "address":"801 L St"},
    {"city":"Seattle, WA",          "lat":47.6062, "lon":-122.3321,"carriers":["Greyhound","FlixBus"],        "address":"611 2nd Ave"},
    {"city":"Portland, OR",         "lat":45.5152, "lon":-122.6784,"carriers":["Greyhound","FlixBus"],        "address":"550 NW Broadway"},
    {"city":"Denver, CO",           "lat":39.7392, "lon":-104.9903,"carriers":["Greyhound","FlixBus"],        "address":"1700 E Colfax Ave"},
    {"city":"Salt Lake City, UT",   "lat":40.7608, "lon":-111.8910,"carriers":["Greyhound","FlixBus"],        "address":"300 S 400 W"},
    {"city":"Las Vegas, NV",        "lat":36.1699, "lon":-115.1398,"carriers":["Greyhound","FlixBus"],        "address":"5100 S Decatur Blvd"},
    {"city":"Boise, ID",            "lat":43.6150, "lon":-116.2023,"carriers":["Greyhound"],                  "address":"501 S Main St"},
    # Hawaii / Alaska (limited)
    {"city":"Honolulu, HI",         "lat":21.3069, "lon":-157.8583,"carriers":["TheHawaiiBus"],               "address":"Ala Moana Center"},
    {"city":"Anchorage, AK",        "lat":61.2181, "lon":-149.9003,"carriers":["Greyhound"],                  "address":"321 E 5th Ave"},
]


def _nearest_intercity_terminals(lat, lon, terminals: List[Dict], n: int = 5) -> List[Dict]:
    """Return the n closest intercity terminals to (lat, lon), with distance added."""
    out = []
    for t in terminals:
        d = _haversine(lat, lon, t["lat"], t["lon"])
        out.append({**t, "dist_mi": round(d, 1)})
    return sorted(out, key=lambda x: x["dist_mi"])[:n]
MODE_COLOURS = {
    "car":       "#2563eb",   # blue
    "foot":      "#16a34a",   # green
    "walk_to":   "#16a34a",   # green
    "walk_from": "#16a34a",   # green
    "ride":      "#9333ea",   # purple
    "drive":     "#2563eb",   # blue
}

MODE_DASH = {
    "car":       None,
    "foot":      "8 4",
    "walk_to":   "8 4",
    "walk_from": "8 4",
    "ride":      None,
    "drive":     None,
}


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _fmt(minutes: float) -> str:
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    return f"{h} hr {m} min" if h else f"{m} min"


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Miles between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 3956 * 2 * asin(sqrt(a))


def _extract_state(address: str) -> Optional[str]:
    US_STATES = {
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL",
        "IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT",
        "NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI",
        "SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
    }
    for p in reversed(address.replace(",", " ").split()):
        if p.strip().upper() in US_STATES:
            return p.strip().upper()
    return None


# ══════════════════════════════════════════════════════════════════════
# GEOCODING
# ══════════════════════════════════════════════════════════════════════

def geocode(address: str) -> Optional[Tuple[float, float]]:
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


# ══════════════════════════════════════════════════════════════════════
# OSRM ROUTING  (car | foot | bicycle — no key)
# ══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def osrm_route(olat, olon, dlat, dlon, profile: str = "car") -> Optional[Dict]:
    """
    Returns dict: distance_mi, duration_min, geometry [[lon,lat],...], steps [str,...]
    """
    url = f"{OSRM_BASE}/{profile}/{olon},{olat};{dlon},{dlat}"
    try:
        r = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "true"},
            timeout=20,
        )
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
                dur_s   = step.get("duration", 0)
                name    = step.get("name", "")
                if instr:
                    label = instr
                    if name:
                        label += f" on {name}"
                    label += f"  ({dist_mi:.2f} mi"
                    if dur_s:
                        label += f", {int(round(dur_s / 60))} min"
                    label += ")"
                    steps.append(label)
        return {
            "distance_mi": round(route["distance"] * 0.000621371, 1),
            "duration_min": round(route["duration"] / 60, 1),
            "geometry": route["geometry"]["coordinates"],
            "steps": steps,
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════
# TRANSIT-STOP DISCOVERY  (Overpass — no key)
# ══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def fetch_transit_stops(lat: float, lon: float, radius_m: int = 8000) -> List[Dict]:
    """
    Pull bus / rail / tram stops near a point.
    Returns [{name, lat, lon, type, ref, operator}, …]
    """
    query = f"""
    [out:json][timeout:12];
    (
      node["highway"="bus_stop"](around:{radius_m},{lat},{lon});
      node["railway"~"station|halt|tram_stop"](around:{radius_m},{lat},{lon});
      node["amenity"="bus_station"](around:{radius_m},{lat},{lon});
      node["public_transport"~"stop|station|platform"](around:{radius_m},{lat},{lon});
      node["amenity"="bus_station"]["operator"~"[Gg]reyhound|[Ff]lix[Bb]us|[Mm]ega[Bb]us"](around:{radius_m},{lat},{lon});
      node["route"~"bus|coach"](around:{radius_m},{lat},{lon});
      way["amenity"="bus_station"](around:{radius_m},{lat},{lon});
      way["public_transport"="station"](around:{radius_m},{lat},{lon});
    );
    out center;
    """
    for ep in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(
                ep,
                data={"data": query},
                headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"},
                timeout=15,
            )
            if r.status_code != 200:
                continue
            raw = r.json()
            for elem in raw.get("elements", []):
                tags = elem.get("tags", {})
                name = tags.get("name", "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                slat = elem.get("lat") or (elem.get("center") or {}).get("lat")
                slon = elem.get("lon") or (elem.get("center") or {}).get("lon")
                if slat is None or slon is None:
                    continue
                # Detect intercity coach first (most specific)
                op = (tags.get("operator") or "").lower()
                is_intercity = any(k in op for k in ("greyhound", "flixbus", "megabus", "coach"))
                if is_intercity or tags.get("route") == "coach":
                    stype = "Intercity Coach"
                elif tags.get("railway") in ("station", "halt"):
                    stype = "Rail"
                elif tags.get("railway") == "tram_stop":
                    stype = "Tram"
                elif tags.get("amenity") == "bus_station":
                    stype = "Bus Station"
                elif tags.get("public_transport") == "platform":
                    stype = "Platform"
                else:
                    stype = "Bus"
                stops.append({
                    "name": name, "lat": slat, "lon": slon,
                    "type": stype,
                    "ref": tags.get("ref", ""),
                    "operator": tags.get("operator", ""),
                })
            return stops
        except Exception:
            continue
    return []


def _nearest_stop(lat, lon, stops: List[Dict]) -> Optional[Dict]:
    best, best_d = None, 99999
    for s in stops:
        d = _haversine(lat, lon, s["lat"], s["lon"])
        if d < best_d:
            best_d, best = d, {**s, "distance_mi": round(d, 2)}
    return best


# ══════════════════════════════════════════════════════════════════════
# TRANSIT ITINERARY  (walk → ride → walk)
# ══════════════════════════════════════════════════════════════════════

def build_transit_itinerary(olat, olon, dlat, dlon,
                            origin_stops, dest_stops) -> Optional[Dict]:
    if not origin_stops or not dest_stops:
        return None
    o_stop = _nearest_stop(olat, olon, origin_stops)
    d_stop = _nearest_stop(dlat, dlon, dest_stops)
    if not o_stop or not d_stop:
        return None

    walk_to   = osrm_route(olat, olon, o_stop["lat"], o_stop["lon"], "foot")
    ride_geom = osrm_route(o_stop["lat"], o_stop["lon"], d_stop["lat"], d_stop["lon"], "car")
    walk_from = osrm_route(d_stop["lat"], d_stop["lon"], dlat, dlon, "foot")

    ride_dist_mi = _haversine(o_stop["lat"], o_stop["lon"], d_stop["lat"], d_stop["lon"])
    ride_min     = round(ride_dist_mi / 25 * 60, 1)

    wt_min = walk_to["duration_min"]   if walk_to   else round(_haversine(olat, olon, o_stop["lat"], o_stop["lon"]) / 3 * 60, 1)
    wf_min = walk_from["duration_min"] if walk_from else round(_haversine(d_stop["lat"], d_stop["lon"], dlat, dlon) / 3 * 60, 1)

    board_buf  = 5
    total_min  = round(wt_min + board_buf + ride_min + wf_min, 1)

    steps = [
        f"Walk to {o_stop['name']} ({o_stop['type']}) — {wt_min:.0f} min",
        f"Board {o_stop['type']} at {o_stop['name']} (allow ~{board_buf} min)",
        f"Ride to {d_stop['name']} — {ride_min:.0f} min ({ride_dist_mi:.1f} mi)",
        f"Walk from {d_stop['name']} to destination — {wf_min:.0f} min",
    ]

    legs = []
    if walk_to:
        legs.append({"mode": "walk_to",   "geometry": walk_to["geometry"],   "label": f"Walk → {o_stop['name']}"})
    legs.append(    {"mode": "ride",       "geometry": ride_geom["geometry"] if ride_geom else [], "label": f"Ride {o_stop['type']}"})
    if walk_from:
        legs.append({"mode": "walk_from", "geometry": walk_from["geometry"], "label": "Walk → Destination"})

    return {
        "legs": legs, "total_min": total_min,
        "total_dist_mi": round(_haversine(olat, olon, dlat, dlon), 1),
        "origin_stop": o_stop, "dest_stop": d_stop, "steps": steps,
    }


# ══════════════════════════════════════════════════════════════════════
# COMBINED ITINERARY  (drive → transit hub → ride → walk)
# ══════════════════════════════════════════════════════════════════════

def build_combined_itinerary(olat, olon, dlat, dlon,
                             origin_stops, dest_stops) -> Optional[Dict]:
    if not origin_stops or not dest_stops:
        return None

    # Prefer Rail > Bus Station > Tram > Bus for hub
    hub = None
    for ptype in ("Rail", "Bus Station", "Tram", "Bus"):
        typed = [s for s in origin_stops if s["type"] == ptype]
        if typed:
            hub = _nearest_stop(olat, olon, typed)
            break
    if hub is None:
        hub = _nearest_stop(olat, olon, origin_stops)
    if hub is None:
        return None

    d_stop = _nearest_stop(dlat, dlon, dest_stops)
    if d_stop is None:
        return None

    drive_leg = osrm_route(olat, olon, hub["lat"], hub["lon"], "car")
    ride_geom = osrm_route(hub["lat"], hub["lon"], d_stop["lat"], d_stop["lon"], "car")
    walk_leg  = osrm_route(d_stop["lat"], d_stop["lon"], dlat, dlon, "foot")

    drive_min = drive_leg["duration_min"] if drive_leg else round(_haversine(olat, olon, hub["lat"], hub["lon"]) / 30 * 60, 1)
    ride_dist = _haversine(hub["lat"], hub["lon"], d_stop["lat"], d_stop["lon"])
    ride_min  = round(ride_dist / 25 * 60, 1)
    walk_min  = walk_leg["duration_min"] if walk_leg else round(_haversine(d_stop["lat"], d_stop["lon"], dlat, dlon) / 3 * 60, 1)

    board_buf  = 5
    total_min  = round(drive_min + board_buf + ride_min + walk_min, 1)

    steps = [
        f"Drive to {hub['name']} ({hub['type']}) — {drive_min:.0f} min",
        f"Park & board {hub['type']} (allow ~{board_buf} min)",
        f"Ride to {d_stop['name']} — {ride_min:.0f} min ({ride_dist:.1f} mi)",
        f"Walk from {d_stop['name']} to destination — {walk_min:.0f} min",
    ]

    legs = []
    if drive_leg:
        legs.append({"mode": "drive",     "geometry": drive_leg["geometry"], "label": f"Drive → {hub['name']}"})
    legs.append(    {"mode": "ride",       "geometry": ride_geom["geometry"] if ride_geom else [], "label": f"Ride {hub['type']}"})
    if walk_leg:
        legs.append({"mode": "walk_from", "geometry": walk_leg["geometry"],  "label": "Walk → Destination"})

    return {
        "legs": legs, "total_min": total_min,
        "total_dist_mi": round(_haversine(olat, olon, dlat, dlon), 1),
        "hub": hub, "dest_stop": d_stop, "steps": steps,
    }


# ══════════════════════════════════════════════════════════════════════
# ROAD-INCIDENT FETCHERS  (nationwide)
# ══════════════════════════════════════════════════════════════════════
# Priority routing:
#   NC  → NC DOT TIMS  (live county incidents, no key)
#   CA  → Caltrans emergency closures via CA Open Data ArcGIS (no key)
#   WA  → WSDOT traveler-info incidents (no key)
#   ALL → Overpass: highway nodes/ways tagged construction / road_work /
#         access=no in a bounding-box around origin ↔ destination.
#         This fires for every state, including the three above, so the
#         user always gets OSM-sourced construction data as a layer.
# ══════════════════════════════════════════════════════════════════════

def _bbox_str(lat1, lon1, lat2, lon2, pad: float = 0.25) -> str:
    """south,west,north,east for Overpass / ArcGIS queries."""
    return (f"{min(lat1,lat2)-pad},{min(lon1,lon2)-pad},"
            f"{max(lat1,lat2)+pad},{max(lon1,lon2)+pad}")


# ── NC DOT TIMS ──────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def fetch_ncdot_incidents(county_name: str) -> List[Dict]:
    cid = NC_COUNTY_IDS.get(county_name.lower().strip())
    if cid is None:
        return []
    url = f"https://eapps.ncdot.gov/services/traffic-prod/v1/counties/{cid}/incidents"
    try:
        r = requests.get(url, headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"}, timeout=10)
        if r.status_code == 200:
            raw = r.json()
            out = []
            for inc in (raw if isinstance(raw, list) else []):
                out.append({
                    "title":     inc.get("title") or inc.get("Title") or inc.get("description") or "Incident",
                    "road":      inc.get("road") or inc.get("Road") or inc.get("roadway") or "",
                    "severity":  inc.get("severity") or inc.get("Severity") or "",
                    "status":    inc.get("status") or inc.get("Status") or "",
                    "latitude":  inc.get("latitude") or inc.get("Latitude"),
                    "longitude": inc.get("longitude") or inc.get("Longitude"),
                    "source":    "NC DOT TIMS",
                })
            return out
    except Exception:
        pass
    return []


# ── Caltrans emergency closures (CA Open Data ArcGIS — no key) ──────
@st.cache_data(ttl=180)
def fetch_caltrans_closures(olat, olon, dlat, dlon) -> List[Dict]:
    south = min(olat, dlat) - 0.3
    north = max(olat, dlat) + 0.3
    west  = min(olon, dlon) - 0.3
    east  = max(olon, dlon) + 0.3
    url   = ("https://gis.dot.ca.gov/arcgis/rest/services/Caltrans/"
             "Caltrans_Emergency_Road_Closures/FeatureServer/0/query")
    params = {
        "where": "1=1",
        "geometry": f"{west},{south},{east},{north}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "COUNTY,ROAD_NAME,CLOSURE_TYPE,DESCRIPTION,LATITUDE,LONGITUDE",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        r = requests.get(url, params=params,
                         headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"}, timeout=12)
        if r.status_code != 200:
            return []
        out = []
        for feat in r.json().get("features", []):
            a = feat.get("properties") or feat.get("attributes") or {}
            out.append({
                "title":     a.get("DESCRIPTION") or a.get("CLOSURE_TYPE") or "Road Closure",
                "road":      a.get("ROAD_NAME", ""),
                "severity":  a.get("CLOSURE_TYPE", ""),
                "status":    "Active",
                "latitude":  a.get("LATITUDE"),
                "longitude": a.get("LONGITUDE"),
                "source":    "Caltrans",
            })
        return out
    except Exception:
        return []


# ── WSDOT traveler-info incidents (WA — no key) ─────────────────────
@st.cache_data(ttl=120)
def fetch_wsdot_incidents(olat, olon, dlat, dlon) -> List[Dict]:
    url = "https://wsdot.wa.gov/trafficapi/rest/Incident/Current"
    try:
        r = requests.get(url,
                         headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"}, timeout=12)
        if r.status_code != 200:
            return []
        raw   = r.json()
        items = raw if isinstance(raw, list) else (raw.get("incidents") or raw.get("Incidents") or [])
        south, north = min(olat,dlat)-0.3, max(olat,dlat)+0.3
        west,  east  = min(olon,dlon)-0.3, max(olon,dlon)+0.3
        out = []
        for inc in items:
            lat = inc.get("Latitude") or inc.get("latitude")
            lon = inc.get("Longitude") or inc.get("longitude")
            if lat is None or lon is None:
                continue
            if not (south <= lat <= north and west <= lon <= east):
                continue
            out.append({
                "title":     inc.get("Description") or inc.get("description") or "Incident",
                "road":      inc.get("LocationDescription") or inc.get("Road") or "",
                "severity":  inc.get("Severity") or inc.get("severity") or "",
                "status":    inc.get("Status") or "Active",
                "latitude":  lat,
                "longitude": lon,
                "source":    "WSDOT",
            })
        return out
    except Exception:
        return []


# ── Overpass: construction / road-work / access=no  (universal) ──────
@st.cache_data(ttl=300)
def fetch_overpass_road_issues(olat, olon, dlat, dlon) -> List[Dict]:
    bb = _bbox_str(olat, olon, dlat, dlon, pad=0.2)
    query = (
        f'[out:json][timeout:15];('
        f'  node["highway"]["construction"]{bb};'
        f'  node["highway"]["access"="no"]{bb};'
        f'  way["highway"]["construction"]{bb};'
        f'  way["highway"]["access"="no"]{bb};'
        f'  node["highway"]["road_work"="yes"]{bb};'
        f'  way["highway"]["road_work"="yes"]{bb};'
        f');out center;'
    )
    for ep in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(ep, data={"data": query},
                headers={"User-Agent": "WiDS-Caregiver-Alert/1.0"}, timeout=18)
            if r.status_code != 200:
                continue
            out = []
            for elem in r.json().get("elements", []):
                tags = elem.get("tags", {})
                lat  = elem.get("lat") or (elem.get("center") or {}).get("lat")
                lon  = elem.get("lon") or (elem.get("center") or {}).get("lon")
                if lat is None or lon is None:
                    continue
                name = tags.get("name", tags.get("highway", "Road"))
                if tags.get("construction"):
                    title = f"Under construction: {tags['construction']}"
                elif tags.get("access") == "no":
                    title = "Access restricted"
                elif tags.get("road_work") == "yes":
                    title = "Road work in progress"
                else:
                    title = "Road issue"
                out.append({
                    "title": title, "road": name,
                    "severity": "Medium", "status": "Active",
                    "latitude": lat, "longitude": lon,
                    "source": "OpenStreetMap",
                })
            return out
        except Exception:
            continue
    return []


# ── Master dispatcher: picks the best source(s) for the detected state
def fetch_road_incidents(state: Optional[str], olat, olon, dlat, dlon,
                         origin_address: str) -> List[Dict]:
    """
    Returns a unified list of incident dicts.  State-specific feeds are
    tried first; Overpass construction tags are always appended so every
    route gets at least OSM-sourced data.
    """
    incidents: List[Dict] = []

    if state == "NC":
        county = CITY_TO_NC_COUNTY.get(
            origin_address.lower().strip().split(",")[0].strip())
        if county:
            incidents.extend(fetch_ncdot_incidents(county))
    elif state == "CA":
        incidents.extend(fetch_caltrans_closures(olat, olon, dlat, dlon))
    elif state == "WA":
        incidents.extend(fetch_wsdot_incidents(olat, olon, dlat, dlon))

    # Always layer on Overpass (works everywhere)
    incidents.extend(fetch_overpass_road_issues(olat, olon, dlat, dlon))
    return incidents


# ══════════════════════════════════════════════════════════════════════
# FIRE PROXIMITY  (checks corridor between origin and destination)
# ══════════════════════════════════════════════════════════════════════

def get_route_fires(olat, olon, dlat, dlon, fire_data, buffer_mi=20) -> List[Dict]:
    if fire_data is None or len(fire_data) == 0:
        return []
    # Sample 5 points along the O→D corridor
    sample_pts = [
        (olat, olon),
        ((olat * 3 + dlat) / 4, (olon * 3 + dlon) / 4),
        ((olat + dlat) / 2,     (olon + dlon) / 2),
        ((olat + dlat * 3) / 4, (olon + dlon * 3) / 4),
        (dlat, dlon),
    ]
    fires, seen = [], set()
    for _, fire in fire_data.iterrows():
        fl, flo = fire.get("latitude"), fire.get("longitude")
        if not fl or not flo:
            continue
        name = fire.get("fire_name", "Satellite Detection")
        if name in seen:
            continue
        min_d = min(_haversine(sp[0], sp[1], fl, flo) for sp in sample_pts)
        if min_d <= buffer_mi:
            seen.add(name)
            acres = fire.get("acres", 0)
            fires.append({
                "name": name, "lat": fl, "lon": flo,
                "acres": acres if (acres and acres == acres) else 0,
                "min_dist_mi": round(min_d, 1),
            })
    fires.sort(key=lambda x: x["min_dist_mi"])
    return fires


# ══════════════════════════════════════════════════════════════════════
# MAP BUILDER
# ══════════════════════════════════════════════════════════════════════

def _add_route_line(m, geom, mode_key, label, is_active):
    if not geom:
        return
    coords  = [[c[1], c[0]] for c in geom]
    weight  = 6 if is_active else 2
    opacity = 0.85 if is_active else 0.3
    colour  = MODE_COLOURS.get(mode_key, "#888")
    dash    = MODE_DASH.get(mode_key)
    kwargs  = dict(color=colour, weight=weight, opacity=opacity, tooltip=label)
    if dash:
        kwargs["dash_array"] = dash
    folium.PolyLine(coords, **kwargs).add_to(m)


def build_map(olat, olon, dlat, dlon,
              car_route, foot_route, transit_itin, combined_itin,
              active_mode, route_fires, incidents,
              origin_stops, dest_stops,
              origin_label, dest_label,
              intercity_terminals=None) -> folium.Map:

    mid_lat, mid_lon = (olat + dlat) / 2, (olon + dlon) / 2
    dist_mi = _haversine(olat, olon, dlat, dlon)
    zoom = 7 if dist_mi > 200 else (8 if dist_mi > 80 else (10 if dist_mi > 30 else 12))

    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=zoom, tiles="CartoDB positron")

    # OSM road overlay (subtle, for road-network context)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OSM Roads",
        opacity=0.25,
    ).add_to(m)

    # ── Origin / Destination ──
    folium.Marker(
        [olat, olon],
        popup=f"<b>START</b><br>{origin_label}",
        icon=folium.Icon(color="green", icon="home", prefix="fa"),
        tooltip="Origin",
    ).add_to(m)
    folium.Marker(
        [dlat, dlon],
        popup=f"<b>DESTINATION</b><br>{dest_label}",
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
        tooltip="Destination",
    ).add_to(m)

    # ── Active route (bold) ──
    if active_mode == "driving" and car_route:
        _add_route_line(m, car_route["geometry"], "car", "Driving", True)
    elif active_mode == "walking" and foot_route:
        _add_route_line(m, foot_route["geometry"], "foot", "Walking", True)
    elif active_mode == "transit" and transit_itin:
        for leg in transit_itin["legs"]:
            _add_route_line(m, leg["geometry"], leg["mode"], leg["label"], True)
    elif active_mode == "combined" and combined_itin:
        for leg in combined_itin["legs"]:
            _add_route_line(m, leg["geometry"], leg["mode"], leg["label"], True)

    # ── Faint inactive routes ──
    if active_mode != "driving" and car_route:
        _add_route_line(m, car_route["geometry"], "car", "Driving (inactive)", False)
    if active_mode != "walking" and foot_route:
        _add_route_line(m, foot_route["geometry"], "foot", "Walking (inactive)", False)

    # ── Transit-stop pins ──
    for stop in origin_stops[:15]:
        folium.CircleMarker(
            [stop["lat"], stop["lon"]], radius=6,
            color="#7c3aed", fill=True, fillColor="#a78bfa", fillOpacity=0.85,
            popup=f"<b>{stop['name']}</b><br>{stop['type']}<br>{stop.get('operator','')}",
            tooltip=f"{stop['type']}: {stop['name']}",
        ).add_to(m)
    for stop in dest_stops[:15]:
        folium.CircleMarker(
            [stop["lat"], stop["lon"]], radius=6,
            color="#7c3aed", fill=True, fillColor="#c4b5fd", fillOpacity=0.85,
            popup=f"<b>{stop['name']}</b><br>{stop['type']}<br>{stop.get('operator','')}",
            tooltip=f"{stop['type']}: {stop['name']}",
        ).add_to(m)

    # ── Intercity-bus terminal pins (teal diamonds) ──
    for t in (intercity_terminals or []):
        carriers = ", ".join(t.get("carriers", []))
        folium.Marker(
            [t["lat"], t["lon"]],
            icon=folium.DivIcon(
                html=f'<div style="font-size:18px;color:#0d9488;text-shadow:0 0 3px #fff;">'
                     f'◆</div>',
                icon_size=(20, 20), icon_anchor=(10, 10),
            ),
            popup=(f"<b>{t['city']}</b><br>"
                   f"<i>Intercity Coach</i><br>"
                   f"{carriers}<br>"
                   f"{t.get('address','')}<br>"
                   f"{t['dist_mi']} mi away"),
            tooltip=f"Coach: {t['city']} ({carriers})",
        ).add_to(m)

    # ── Fire circles ──
    for f in route_fires:
        acres = f.get("acres", 100) or 100
        folium.Circle(
            [f["lat"], f["lon"]],
            radius=max(int(acres * 40), 1000),
            color="red", fill=True, fillColor="orange", fillOpacity=0.35,
            popup=f"<b>{f['name']}</b><br>{f['min_dist_mi']} mi from route<br>{acres:,.0f} acres",
            tooltip=f"FIRE: {f['name']}",
        ).add_to(m)

    # ── Road-incident pins ──
    for inc in incidents[:8]:
        title = (inc.get("title") or inc.get("Title") or
                 inc.get("description") or inc.get("Description") or "Incident")
        sev   = inc.get("severity") or inc.get("Severity") or ""
        ilat  = inc.get("latitude") or inc.get("Latitude")
        ilon  = inc.get("longitude") or inc.get("Longitude")
        if ilat and ilon:
            folium.Marker(
                [float(ilat), float(ilon)],
                popup=f"<b>Road Incident</b><br>{title}<br>Severity: {sev}",
                icon=folium.Icon(color="orange", icon="exclamation-triangle", prefix="fa"),
                tooltip=f"Incident: {title}",
            ).add_to(m)

    # ── Legend ──
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
         background:white;padding:14px 18px;border-radius:10px;
         border:2px solid #ccc;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.25);
         font-family:sans-serif;">
     <b style="font-size:14px;">Legend</b><br><br>
     <span style="color:#2563eb;font-size:18px;">━━</span> Driving &nbsp;&nbsp;
     <span style="color:#16a34a;font-size:18px;">╌╌</span> Walking &nbsp;&nbsp;
     <span style="color:#9333ea;font-size:18px;">━━</span> Transit Ride<br><br>
     <span style="color:red;font-size:16px;">●</span> Fire Zone &nbsp;&nbsp;
     <span style="color:#7c3aed;font-size:14px;">●</span> Transit Stop &nbsp;&nbsp;
     <span style="color:#0d9488;font-size:14px;">◆</span> Intercity Coach &nbsp;&nbsp;
     <span style="color:orange;font-size:14px;">▲</span> Road Incident
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


# ══════════════════════════════════════════════════════════════════════
# MAIN PAGE RENDERER
# ══════════════════════════════════════════════════════════════════════

def render_directions_page(fire_data, vulnerable_populations):
    """Entry point called by the multi-page dashboard."""

    st.title("Directions & Navigation")
    st.markdown(
        "Plan your route with real-time transit stops, fire-danger zones, "
        "and road-closure warnings — driving, walking, public transit, or a combined trip."
    )

    # ── session-state init ──
    for k, v in {
        "dir_origin": "", "dir_dest": "",
        "dir_origin_coords": None, "dir_dest_coords": None,
        "dir_triggered": False,
        "dir_origin_stops": None, "dir_dest_stops": None,
    }.items():
        st.session_state.setdefault(k, v)

    # ── Input row ──
    col_o, col_d, col_btn = st.columns([3, 3, 1])
    with col_o:
        origin_input = st.text_input("Origin", value=st.session_state.dir_origin,
                                     placeholder="e.g. Los Angeles, CA", key="dir_origin_input")
    with col_d:
        dest_input = st.text_input("Destination", value=st.session_state.dir_dest,
                                   placeholder="e.g. San Francisco, CA", key="dir_dest_input")
    with col_btn:
        go_btn = st.button("Get Directions", type="primary")

    if go_btn and origin_input.strip() and dest_input.strip():
        st.session_state.dir_origin = origin_input.strip()
        st.session_state.dir_dest   = dest_input.strip()
        st.session_state.dir_triggered = True
        st.session_state.dir_origin_coords = None
        st.session_state.dir_dest_coords   = None
        st.session_state.dir_origin_stops  = None
        st.session_state.dir_dest_stops    = None

    # ── Landing state ──
    if not st.session_state.dir_triggered:
        st.markdown("---")
        st.info(
            "Enter an origin and destination above, then click **Get Directions**.\n\n"
            "This planner shows real transit stops (OpenStreetMap), fires along your route, "
            "and live road-closure data (NC DOT, Caltrans, WSDOT, + OpenStreetMap everywhere). Routes come from the open-source OSRM engine."
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Driving", "OSRM car", "turn-by-turn")
        c2.metric("Walking", "OSRM foot", "step-by-step")
        c3.metric("Transit", "OSM stops", "walk+ride+walk")
        c4.metric("Combined", "Drive+Ride", "best of both")
        return

    # ── Geocode ──
    if st.session_state.dir_origin_coords is None:
        with st.spinner("Geocoding origin…"):
            st.session_state.dir_origin_coords = geocode(st.session_state.dir_origin)
    if st.session_state.dir_dest_coords is None:
        with st.spinner("Geocoding destination…"):
            st.session_state.dir_dest_coords = geocode(st.session_state.dir_dest)

    o_coords = st.session_state.dir_origin_coords
    d_coords = st.session_state.dir_dest_coords

    if not o_coords:
        st.error("Origin not found. Try 'City, State' format.")
        return
    if not d_coords:
        st.error("Destination not found. Try 'City, State' format.")
        return

    olat, olon = o_coords
    dlat, dlon = d_coords
    straight_mi = _haversine(olat, olon, dlat, dlon)

    c1, c2 = st.columns(2)
    c1.success(f"Origin: **{st.session_state.dir_origin.title()}**  ({olat:.4f}, {olon:.4f})")
    c2.success(f"Destination: **{st.session_state.dir_dest.title()}**  ({dlat:.4f}, {dlon:.4f})")
    st.caption(f"Straight-line distance: {straight_mi:.1f} mi")

    # ── Fetch transit stops ──
    if st.session_state.dir_origin_stops is None:
        with st.spinner("Finding transit stops near origin…"):
            st.session_state.dir_origin_stops = fetch_transit_stops(olat, olon)
    if st.session_state.dir_dest_stops is None:
        with st.spinner("Finding transit stops near destination…"):
            st.session_state.dir_dest_stops = fetch_transit_stops(dlat, dlon)

    origin_stops = st.session_state.dir_origin_stops or []
    dest_stops   = st.session_state.dir_dest_stops or []

    # ── Nearest intercity-bus terminals (static seed + any OSM coach stops) ──
    nearby_intercity = _nearest_intercity_terminals(olat, olon, INTERCITY_TERMINALS, n=5)
    # Also pull any Overpass-discovered intercity stops into the list
    for s in origin_stops:
        if s["type"] == "Intercity Coach" and not any(
                t["city"].lower().startswith(s["name"].lower()[:8]) for t in nearby_intercity):
            nearby_intercity.append({
                "city": s["name"], "lat": s["lat"], "lon": s["lon"],
                "carriers": [s.get("operator", "Coach")],
                "address": "", "dist_mi": round(_haversine(olat, olon, s["lat"], s["lon"]), 1),
            })
    nearby_intercity = sorted(nearby_intercity, key=lambda x: x["dist_mi"])[:6]

    # ── Compute all routes ──
    with st.spinner("Calculating routes…"):
        car_route     = osrm_route(olat, olon, dlat, dlon, "car")
        foot_route    = osrm_route(olat, olon, dlat, dlon, "foot")
        transit_itin  = build_transit_itinerary(olat, olon, dlat, dlon, origin_stops, dest_stops)
        combined_itin = build_combined_itinerary(olat, olon, dlat, dlon, origin_stops, dest_stops)

    # ── Fires along route ──
    route_fires = get_route_fires(olat, olon, dlat, dlon, fire_data, buffer_mi=20)

    # ── Road incidents (nationwide) ──
    state_o = _extract_state(st.session_state.dir_origin)
    with st.spinner("Checking road conditions…"):
        incidents = fetch_road_incidents(
            state_o, olat, olon, dlat, dlon, st.session_state.dir_origin)

    # ── Fire warning ──
    if route_fires:
        st.warning(
            f"**{len(route_fires)} active fire(s) detected along or near your route.**  "
            "Fire zones are shown on the map. Consider alternate routes if possible."
        )
        for f in route_fires[:4]:
            st.caption(f"  • {f['name']} — {f['min_dist_mi']} mi from route ({f['acres']:,.0f} acres)")

    # ── Road-incident advisory (nationwide) ──
    st.markdown("---")
    st.subheader("Road Conditions")

    if incidents:
        # Group by source so NC / CA / WA / OSM labels are clear
        by_source: Dict[str, List[Dict]] = {}
        for inc in incidents:
            by_source.setdefault(inc.get("source", "Other"), []).append(inc)

        st.warning(
            f"**{len(incidents)} road issue(s) found along your route**  "
            f"(updated {datetime.now().strftime('%H:%M')})."
        )
        for source, group in by_source.items():
            st.markdown(f"**{source}** — {len(group)} issue(s)")
            for inc in group[:6]:
                title = inc.get("title", "Incident")
                road  = inc.get("road", "")
                sev   = inc.get("severity", "")
                line  = f"  • {title}"
                if road:   line += f" — {road}"
                if sev:    line += f"  [{sev}]"
                st.caption(line)
            if len(group) > 6:
                st.caption(f"  … and {len(group)-6} more.")
    else:
        st.success("No road issues detected along your route right now.")

    # Always show the correct state DOT link for origin
    if state_o and state_o in STATE_DOT_LINKS:
        dot = STATE_DOT_LINKS[state_o]
        st.caption(
            f"Full {dot['name']} conditions: "
            f"[{dot['name']} DOT]({dot['url']})  •  Call **511** anywhere in the US."
        )
    else:
        st.caption("Call **511** from anywhere in the US for real-time road conditions.")

    # ── Summary metrics ──
    drive_eta  = car_route["duration_min"]  if car_route  else round(straight_mi * 1.3 / 45 * 60, 0)
    drive_dist = car_route["distance_mi"]   if car_route  else round(straight_mi * 1.3, 1)
    walk_eta   = foot_route["duration_min"] if foot_route else round(straight_mi * 1.2 / 3.5 * 60, 0)
    walk_dist  = foot_route["distance_mi"]  if foot_route else round(straight_mi * 1.2, 1)

    # ── MODE TABS ──
    st.markdown("---")

    tab_labels = [
        f"Driving  ({_fmt(drive_eta)})",
        f"Walking  ({_fmt(walk_eta)})",
    ]
    if transit_itin:
        tab_labels.append(f"Transit  ({_fmt(transit_itin['total_min'])})")
    if combined_itin:
        tab_labels.append(f"Combined  ({_fmt(combined_itin['total_min'])})")
    tab_labels.append("Intercity Bus")

    tabs = st.tabs(tab_labels)
    active_mode = "driving"

    # ── TAB: DRIVING ──
    with tabs[0]:
        active_mode = "driving"
        st.subheader("Driving Directions")
        ca, cb = st.columns(2)
        ca.metric("Distance", f"{drive_dist} mi")
        cb.metric("ETA", _fmt(drive_eta))

        if car_route and car_route["steps"]:
            st.markdown("**Turn-by-Turn**")
            for i, step in enumerate(car_route["steps"][:25], 1):
                st.write(f"{i}. {step}")
            if len(car_route["steps"]) > 25:
                st.caption(f"… and {len(car_route['steps']) - 25} more steps.")
        else:
            st.info("Turn-by-turn data unavailable from OSRM right now. Use the map below.")
        st.markdown("**Tips:** Check **511** or your state DOT for closures. Fill up gas. Carry water.")

    # ── TAB: WALKING ──
    with tabs[1]:
        active_mode = "walking"
        st.subheader("Walking Directions")
        ca, cb = st.columns(2)
        ca.metric("Distance", f"{walk_dist} mi")
        cb.metric("ETA", _fmt(walk_eta))
        if walk_dist > 25:
            st.warning("This route is over 25 miles on foot — consider driving or transit instead.")
        if foot_route and foot_route["steps"]:
            st.markdown("**Step-by-Step**")
            for i, step in enumerate(foot_route["steps"][:25], 1):
                st.write(f"{i}. {step}")
            if len(foot_route["steps"]) > 25:
                st.caption(f"… and {len(foot_route['steps']) - 25} more steps.")
        else:
            st.info("Walking step data unavailable from OSRM. Use the map below.")
        st.markdown("**Tips:** Wear sturdy shoes. Carry water. Stay on sidewalks. If fires are nearby, shelter and call 911.")

    # ── TAB: TRANSIT ──
    tidx = 2
    if transit_itin and tidx < len(tabs):
        with tabs[tidx]:
            active_mode = "transit"
            st.subheader("Public Transit Route")
            ca, cb, cc = st.columns(3)
            ca.metric("Total Time", _fmt(transit_itin["total_min"]))
            cb.metric("Board At", transit_itin["origin_stop"]["name"])
            cc.metric("Exit At", transit_itin["dest_stop"]["name"])

            st.markdown("**Itinerary**")
            for i, step in enumerate(transit_itin["steps"], 1):
                st.write(f"{i}. {step}")

            st.warning(
                "Live transit schedules are not included in this tool. "
                "Check your local transit agency app for real departure times. "
                "Transit may be suspended during active emergencies."
            )
            if origin_stops:
                st.markdown("**Nearby Stops (Origin)**")
                for s in sorted(origin_stops, key=lambda x: _haversine(olat, olon, x["lat"], x["lon"]))[:6]:
                    d = _haversine(olat, olon, s["lat"], s["lon"])
                    line = f"  {s['type']}  •  {s['name']}  •  {d:.2f} mi"
                    if s.get("operator"):
                        line += f"  •  {s['operator']}"
                    st.caption(line)
            tidx += 1

    # ── TAB: COMBINED ──
    if combined_itin and tidx < len(tabs):
        with tabs[tidx]:
            active_mode = "combined"
            st.subheader("Drive + Transit (Combined)")
            ca, cb, cc = st.columns(3)
            ca.metric("Total Time", _fmt(combined_itin["total_min"]))
            cb.metric("Drive to", combined_itin["hub"]["name"])
            cc.metric("Exit at", combined_itin["dest_stop"]["name"])

            st.markdown("**Itinerary**")
            for i, step in enumerate(combined_itin["steps"], 1):
                st.write(f"{i}. {step}")
            st.info("Drive to the transit hub, park, board, ride to near your destination, then walk.")
            tidx += 1

    # ── TAB: INTERCITY BUS ──
    if tidx < len(tabs):
        with tabs[tidx]:
            st.subheader("Intercity Bus Options")
            st.caption(
                "Greyhound, FlixBus, and Megabus terminals near your origin. "
                "Book tickets directly on each carrier's site or app before departing."
            )

            if nearby_intercity:
                for t in nearby_intercity:
                    carriers = ", ".join(t.get("carriers", []))
                    addr     = t.get("address", "")
                    dist     = t.get("dist_mi", "?")
                    st.markdown(
                        f"**{t['city']}** — {dist} mi away\n"
                        f"Carriers: {carriers}\n"
                        f"Address: {addr}"
                    )
                    # Booking links
                    links = []
                    for c in t.get("carriers", []):
                        cl = c.lower()
                        if "greyhound" in cl:
                            links.append("[Greyhound](https://www.greyhoundlines.com/en-us/)")
                        elif "flixbus" in cl:
                            links.append("[FlixBus](https://www.flixbus.com/)")
                        elif "megabus" in cl:
                            links.append("[Megabus](https://us.megabus.com/)")
                    if links:
                        st.caption("Book:  " + "  •  ".join(links))
                    st.markdown("---")
            else:
                st.info("No intercity terminals found near your origin. Check greyhoundlines.com or flixbus.com directly.")

            st.warning(
                "Schedules and availability are not shown here — always confirm departure times "
                "on the carrier's website or app before heading to the terminal. "
                "Service may be limited or suspended during active wildfire emergencies."
            )

    # ── COMPARISON TABLE ──
    st.markdown("---")
    st.subheader("Mode Comparison")
    rows = [
        {"Mode": "Driving",  "Distance": f"{drive_dist} mi", "ETA": _fmt(drive_eta),
         "Notes": "Fastest for most intercity. Check 511 for closures."},
        {"Mode": "Walking",  "Distance": f"{walk_dist} mi",  "ETA": _fmt(walk_eta),
         "Notes": "Practical under ~10 mi. Watch for fire zones."},
    ]
    if transit_itin:
        rows.append({"Mode": "Transit", "Distance": f"{transit_itin['total_dist_mi']} mi",
                     "ETA": _fmt(transit_itin["total_min"]),
                     "Notes": f"Walk → {transit_itin['origin_stop']['name']} → ride → {transit_itin['dest_stop']['name']} → walk."})
    if combined_itin:
        rows.append({"Mode": "Combined", "Distance": f"{combined_itin['total_dist_mi']} mi",
                     "ETA": _fmt(combined_itin["total_min"]),
                     "Notes": f"Drive → {combined_itin['hub']['name']} → ride → {combined_itin['dest_stop']['name']} → walk."})
    if nearby_intercity:
        rows.append({"Mode": "Intercity Bus", "Distance": f"{nearby_intercity[0]['dist_mi']} mi to terminal",
                     "ETA": "Varies by schedule",
                     "Notes": f"Nearest: {nearby_intercity[0]['city']} ({', '.join(nearby_intercity[0]['carriers'])}). Book online."})
    st.table(rows)

    # ── INTERACTIVE MAP ──
    st.markdown("---")
    st.subheader("Route Map")
    st.caption("Active route is bold; faint lines = other available modes. Red/orange = fire zones. Purple dots = transit stops. Teal diamonds = intercity coach terminals.")

    m = build_map(
        olat, olon, dlat, dlon,
        car_route, foot_route, transit_itin, combined_itin,
        active_mode=active_mode,
        route_fires=route_fires,
        incidents=incidents,
        origin_stops=origin_stops,
        dest_stops=dest_stops,
        origin_label=st.session_state.dir_origin.title(),
        dest_label=st.session_state.dir_dest.title(),
        intercity_terminals=nearby_intercity,
    )
    st_folium(m, width="100%", height=650)

    # ── Emergency footer ──
    st.markdown("---")
    st.subheader("Emergency Resources")
    e1, e2, e3 = st.columns(3)
    e1.markdown("**Emergency Lines**\n- 911 — Fire / Police / Medical\n- 211 — Evacuation assistance\n- 511 — Road conditions\n- 988 — Crisis Lifeline")
    e2.markdown("**Before You Go**\n- Check road conditions (511)\n- Fill gas tank\n- Download offline maps\n- Carry water + snacks")
    e3.markdown("**Data Sources**\n- Routes: OSRM (open-source)\n- Stops: OpenStreetMap Overpass\n- Road issues: State DOTs + OSM\n- Map: OpenStreetMap / CartoDB")


# ── standalone test ──────────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(page_title="Directions & Navigation", layout="wide")
    render_directions_page(None, None)