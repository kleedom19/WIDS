import streamlit as st
import pandas as pd
import os

st.title("🔥 Wildfire Caregiver Alert System")
st.markdown("### Reducing Evacuation Delays for Vulnerable Populations")

# Load data
try:
    df = pd.read_csv('../01_raw_data/processed/fire_events_with_svi_and_delays.csv')
    
    st.metric("Fire Events Analyzed", len(df))
    st.metric("Events with Vulnerability Data", df['RPL_THEMES'].notna().sum())
    
    # Show key statistics
    vulnerable = df[df['RPL_THEMES'] >= 0.5]['evacuation_delay_hours'].dropna()
    non_vulnerable = df[df['RPL_THEMES'] < 0.5]['evacuation_delay_hours'].dropna()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Vulnerable Pop. Avg Delay", f"{vulnerable.mean():.1f} hrs")
    col2.metric("Non-Vulnerable Avg Delay", f"{non_vulnerable.mean():.1f} hrs")
    col3.metric("Disparity Gap", f"{vulnerable.mean() - non_vulnerable.mean():.1f} hrs")
    
except Exception as e:
    st.error(f"Error loading data: {e}")

# Show visualizations
st.subheader("📊 Key Findings")

if os.path.exists('disparity_analysis.png'):
    st.image('disparity_analysis.png', caption="Evacuation Delay Disparities")
    
if os.path.exists('caregiver_impact.png'):
    st.image('caregiver_impact.png', caption="Projected Impact of Caregiver Alerts")
    
if os.path.exists('feature_importance.png'):
    st.image('feature_importance.png', caption="Key Vulnerability Factors")

st.subheader("📈 Sample Data")
try:
    st.write(df.head(10))
except:
    pass
