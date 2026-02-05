import os
import pandas as pd
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

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

    # Check if 'geo_event_id', 'lat', and 'lng' columns exist before cleaning
    if 'geo_event_id' in geo_events_df.columns and 'lat' in geo_events_df.columns and 'lng' in geo_events_df.columns:
        # Drop rows with missing values in these columns
        geo_events_df = geo_events_df.dropna(subset=['geo_event_id', 'lat', 'lng'])
    else:
        st.warning("Columns 'geo_event_id', 'lat', and/or 'lng' not found in geo_events_df.")

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
        import pydeck as pdk
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
    
    # Perform basic descriptive statistics for evac_zones_df
    st.subheader("Descriptive Statistics for Evacuation Zones Data")
    st.write(evac_zones_df.describe())

    # Check for missing values in evac_zones_df
    st.subheader("Missing Values in Evacuation Zones Data")
    st.write(evac_zones_df.isnull().sum())

    # Show the unique values of 'status' and 'region_id' for evacuation zones
    st.subheader("Unique Values in 'status' and 'region_id' Columns")
    st.write(evac_zones_df[['status', 'region_id']].nunique())

    # Show distribution of 'status' column (categorical data)
    st.subheader("Distribution of 'status' in Evacuation Zones")
    st.write(evac_zones_df['status'].value_counts())

    # Map of evacuation zones using pydeck
    st.subheader("Map of Evacuation Zones")
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
