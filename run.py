import os
import pandas as pd
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
from shapely import wkt
import pydeck as pdk

# Load environment variables for Supabase connection
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Streamlit page setup
st.set_page_config(page_title="WiDS Wildfire Data Dashboard", layout="wide")
st.title("WiDS Wildfire Data Dashboard")
st.caption("Benchmarks response timing against historical patterns and flags incidents with dangerous delays.")

# Check if the Supabase credentials are available
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_KEY. Check your local .env (do not commit it).")
    st.stop()

# Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fetch data from Supabase
def fetch_data_from_supabase():
    try:
        # Query the 'geo_events_geoevent' table
        geo_events_response = supabase.table('geo_events_geoevent').select('*').execute()
        geo_events_data = geo_events_response.data  # Correct way to access the data

        # Query the 'evac_zones_gis_evaczone' table
        evac_zones_response = supabase.table('evac_zones_gis_evaczone').select('*').execute()
        evac_zones_data = evac_zones_response.data  # Correct way to access the data

        # Convert data to pandas DataFrame
        geo_events_df = pd.DataFrame(geo_events_data)
        evac_zones_df = pd.DataFrame(evac_zones_data)

        return geo_events_df, evac_zones_df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None, None

# Get the data
geo_events_df, evac_zones_df = fetch_data_from_supabase()

# If the data was fetched successfully, perform EDA
if geo_events_df is not None and evac_zones_df is not None:
    st.subheader("Geo Events Data")
    
    # Show first few rows of geo_events_df for inspection
    st.write(geo_events_df.head())

    # Check the columns of the geo_events_df before cleaning
    st.write("Columns in geo_events_df:", geo_events_df.columns)

    # Perform basic descriptive statistics for geo_events_df
    st.subheader("Descriptive Statistics for Geo Events Data")
    st.write(geo_events_df.describe())

    # Check for missing values in geo_events_df
    st.subheader("Missing Values in Geo Events Data")
    st.write(geo_events_df.isnull().sum())

    # Show the unique values of some important columns for inspection
    st.subheader("Unique Values in 'geo_event_type' and 'is_active' Columns")
    st.write(geo_events_df[['geo_event_type', 'is_active']].nunique())

    # Show distribution of the 'geo_event_type' column (categorical data)
    st.subheader("Distribution of 'geo_event_type'")
    st.write(geo_events_df['geo_event_type'].value_counts())

    # Visualize latitude and longitude of geo events on a map using pydeck
    st.subheader("Map of Geo Events")
    if not geo_events_df.empty:
        geo_events_map = pdk.Deck(
            initial_view_state=pdk.ViewState(
                latitude=geo_events_df['lat'].mean(),
                longitude=geo_events_df['lng'].mean(),
                zoom=6,
            ),
            layers=[
                pdk.Layer(
                    'ScatterplotLayer',
                    data=geo_events_df,
                    get_position='[lng, lat]',
                    get_color='[200, 30, 0, 160]',
                    get_radius=200,
                )
            ]
        )
        st.pydeck_chart(geo_events_map)
    else:
        st.warning("No data available for mapping.")

    # Show the first few rows of the evacuation zones data for inspection
    st.subheader("Evacuation Zones Data")
    st.write(evac_zones_df.head())

    # Remove 'SRID=4326;' from the 'geom' column and convert to shapely geometry
    if 'geom' in evac_zones_df.columns:
        # Strip 'SRID=4326;' from the geometry string
        evac_zones_df['geom'] = evac_zones_df['geom'].apply(lambda x: x.replace('SRID=4326;', '') if isinstance(x, str) else x)

        # Convert the 'geom' field (geometry) to lat/lng
        evac_zones_df['geometry'] = evac_zones_df['geom'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else None)
        evac_zones_df['lat'] = evac_zones_df['geometry'].apply(lambda x: x.centroid.y if x is not None else None)
        evac_zones_df['lng'] = evac_zones_df['geometry'].apply(lambda x: x.centroid.x if x is not None else None)

    # Check if lat/lng are now available
    st.write("Columns after processing geometry: ", evac_zones_df.columns)
    
    # Check for missing values in the new lat, lng columns
    st.subheader("Missing Values in 'lat' and 'lng' Columns")
    st.write(evac_zones_df[['lat', 'lng']].isnull().sum())

    # Map of evacuation zones using pydeck
    st.subheader("Map of Evacuation Zones")
    if 'lat' in evac_zones_df.columns and 'lng' in evac_zones_df.columns:
        if not evac_zones_df.empty:
            evac_zones_map = pdk.Deck(
                initial_view_state=pdk.ViewState(
                    latitude=evac_zones_df['lat'].mean(),
                    longitude=evac_zones_df['lng'].mean(),
                    zoom=6,
                ),
                layers=[
                    pdk.Layer(
                        'ScatterplotLayer',
                        data=evac_zones_df,
                        get_position='[lng, lat]',
                        get_color='[0, 200, 255, 160]',
                        get_radius=200,
                    )
                ]
            )
            st.pydeck_chart(evac_zones_map)
        else:
            st.warning("No data available for mapping.")
    else:
        st.warning("Latitude and Longitude columns are missing or incomplete.")
