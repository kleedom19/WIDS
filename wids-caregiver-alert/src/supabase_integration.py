"""
supabase_integration.py

Supabase data layer for WiDS Fire Watch Dashboard.
Provides cached data loading from Supabase tables with fallback to local CSVs.

Installation:
    pip install supabase --break-system-packages

Setup in Supabase:
    1. Create tables:
       - fire_events (id, fire_name, latitude, longitude, acres, timestamp, state)
       - svi_data (id, county, state, fips, svi_score, population, vulnerable_count)
       - road_incidents (id, title, latitude, longitude, severity, source, timestamp)
    
    2. Upload CSVs via Supabase Table Editor or SQL:
       - SVI_2022_US_county.csv → svi_data
       - fire_events_with_svi_and_delays.csv → fire_events
    
    3. Add RLS policies (or disable for datathon):
       ALTER TABLE fire_events ENABLE ROW LEVEL SECURITY;
       CREATE POLICY "Public read" ON fire_events FOR SELECT USING (true);
"""

import os
import streamlit as st
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime, timedelta

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️  supabase-py not installed. Run: pip install supabase --break-system-packages")


# ══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

SUPABASE_URL = "https://fguvvhqvzifnsihhomcv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZndXZ2aHF2emlmbnNpaGhvbWN2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg2MDg0NTksImV4cCI6MjA1NDE4NDQ1OX0.pZW1i4cJYBWhRvIXA_tV5g_7RglHWF5kdR6xbj3VkeM"

# Fallback to local CSVs if Supabase fails
_HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_FALLBACKS = {
    "svi": [
        os.path.join(_HERE, "..", "..", "..", "01_raw_data", "external", "SVI_2022_US_county.csv"),
        os.path.join(_HERE, "..", "..", "01_raw_data", "external", "SVI_2022_US_county.csv"),
        os.path.join(_HERE, "..", "01_raw_data", "external", "SVI_2022_US_county.csv"),
    ],
    "fires": [
        os.path.join(_HERE, "..", "..", "..", "01_raw_data", "processed", "fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE, "..", "..", "01_raw_data", "processed", "fire_events_with_svi_and_delays.csv"),
        os.path.join(_HERE, "..", "01_raw_data", "processed", "fire_events_with_svi_and_delays.csv"),
    ],
}


# ══════════════════════════════════════════════════════════════════════
# CLIENT INITIALIZATION
# ══════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_supabase_client() -> Optional[Client]:
    """Initialize Supabase client (cached across app)."""
    if not SUPABASE_AVAILABLE:
        return None
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Test connection
        client.table("fire_events").select("id").limit(1).execute()
        return client
    except Exception as e:
        st.sidebar.warning(f"Supabase unavailable: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)  # 5-minute cache
def load_svi_from_supabase() -> Optional[pd.DataFrame]:
    """Load SVI data from Supabase with fallback to local CSV."""
    client = get_supabase_client()
    
    # Try Supabase first
    if client:
        try:
            response = client.table("svi_data").select("*").execute()
            if response.data:
                df = pd.DataFrame(response.data)
                st.sidebar.success(f"✓ SVI loaded from Supabase ({len(df)} counties)")
                return df
        except Exception as e:
            st.sidebar.warning(f"Supabase SVI fetch failed: {e}")
    
    # Fallback to local CSV
    for path in LOCAL_FALLBACKS["svi"]:
        real_path = os.path.realpath(path)
        if os.path.exists(real_path):
            try:
                df = pd.read_csv(real_path)
                st.sidebar.info(f"✓ SVI loaded from local CSV ({len(df)} counties)")
                return df
            except Exception as e:
                continue
    
    st.sidebar.error("❌ SVI data not found (Supabase or local)")
    return None


@st.cache_data(ttl=300)
def load_fires_from_supabase() -> Optional[pd.DataFrame]:
    """Load fire events from Supabase with fallback."""
    client = get_supabase_client()
    
    if client:
        try:
            response = client.table("fire_events").select("*").execute()
            if response.data:
                df = pd.DataFrame(response.data)
                st.sidebar.success(f"✓ Fires loaded from Supabase ({len(df)} events)")
                return df
        except Exception as e:
            st.sidebar.warning(f"Supabase fires fetch failed: {e}")
    
    # Fallback
    for path in LOCAL_FALLBACKS["fires"]:
        real_path = os.path.realpath(path)
        if os.path.exists(real_path):
            try:
                df = pd.read_csv(real_path)
                st.sidebar.info(f"✓ Fires loaded from local CSV ({len(df)} events)")
                return df
            except Exception as e:
                continue
    
    st.sidebar.error("❌ Fire data not found")
    return None


@st.cache_data(ttl=120)  # 2-minute cache for real-time incidents
def load_road_incidents_from_supabase(state: Optional[str] = None) -> List[Dict]:
    """Load road incidents from Supabase (real-time data)."""
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        query = client.table("road_incidents").select("*")
        if state:
            query = query.eq("state", state)
        
        # Only recent incidents (last 24 hours)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        query = query.gte("timestamp", cutoff)
        
        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        st.sidebar.warning(f"Road incidents fetch failed: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
# WRITE OPERATIONS (for logging/alerts)
# ══════════════════════════════════════════════════════════════════════

def log_evacuation_alert(county: str, fire_name: str, alert_type: str, 
                        message: str, language: str = "en") -> bool:
    """Log an evacuation alert to Supabase for tracking."""
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        data = {
            "county": county,
            "fire_name": fire_name,
            "alert_type": alert_type,
            "message": message,
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
        }
        client.table("evacuation_alerts").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Alert logging failed: {e}")
        return False


def log_route_request(origin: str, destination: str, mode: str, 
                      fire_proximity_miles: float) -> bool:
    """Log route requests for analytics."""
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        data = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "fire_proximity_miles": fire_proximity_miles,
            "timestamp": datetime.utcnow().isoformat(),
        }
        client.table("route_requests").insert(data).execute()
        return True
    except Exception:
        return False  # Fail silently for analytics


# ══════════════════════════════════════════════════════════════════════
# HELPER: VULNERABLE POPULATIONS (replaces load_vulnerable_populations)
# ══════════════════════════════════════════════════════════════════════

def get_vulnerable_populations() -> Dict:
    """
    Load SVI data and return vulnerable populations dict.
    Replaces the load_vulnerable_populations() function in the main dashboard.
    """
    svi = load_svi_from_supabase()
    if svi is None:
        # Fallback mock data
        return {
            'Los Angeles County, CA': {'lat': 34.0522, 'lon': -118.2437, 'vulnerable_count': 523, 'svi_score': 0.95},
            'Maricopa County, AZ':    {'lat': 33.4484, 'lon': -112.0740, 'vulnerable_count': 456, 'svi_score': 0.89},
            'King County, WA':        {'lat': 47.6062, 'lon': -122.3321, 'vulnerable_count': 412, 'svi_score': 0.82},
        }
    
    # Filter high-vulnerability counties (SVI >= 0.75)
    vulnerable = svi[svi['RPL_THEMES'] >= 0.75].copy() if 'RPL_THEMES' in svi.columns else svi.head(200)
    
    result = {}
    for _, row in vulnerable.iterrows():
        county_name = f"{row.get('COUNTY', 'Unknown')}, {row.get('ST_ABBR', 'XX')}"
        result[county_name] = {
            'lat': float(row.get('LAT', 0)),
            'lon': float(row.get('LON', 0)),
            'vulnerable_count': int(row.get('E_TOTPOP', 0) * row.get('RPL_THEMES', 0.5)),
            'svi_score': float(row.get('RPL_THEMES', 0.5)),
        }
    
    # Sort by SVI score descending, limit to top 200
    result = dict(sorted(result.items(), key=lambda x: x[1]['svi_score'], reverse=True)[:200])
    return result


# ══════════════════════════════════════════════════════════════════════
# USAGE EXAMPLES
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test connection
    print("Testing Supabase connection...")
    
    svi = load_svi_from_supabase()
    print(f"SVI records: {len(svi) if svi is not None else 0}")
    
    fires = load_fires_from_supabase()
    print(f"Fire events: {len(fires) if fires is not None else 0}")
    
    incidents = load_road_incidents_from_supabase("NC")
    print(f"NC road incidents: {len(incidents)}")
    
    vulns = get_vulnerable_populations()
    print(f"Vulnerable counties: {len(vulns)}")
    print(f"Top 3: {list(vulns.keys())[:3]}")