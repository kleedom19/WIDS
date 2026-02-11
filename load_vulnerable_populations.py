"""
load_vulnerable_populations.py

Loads CDC Social Vulnerability Index (SVI) data and creates
a comprehensive vulnerable populations dataset for the dashboard.

This replaces the hardcoded 6 locations with HUNDREDS of real
vulnerable counties across the USA.
"""

import pandas as pd
import json

def load_cdc_svi_data(filepath='../01_raw_data/external/SVI_2022_US_county.csv'):
    """
    Load CDC SVI data and extract highly vulnerable counties
    
    Returns:
    --------
    Dictionary of vulnerable locations:
    {
        'County Name, State': {
            'lat': float,
            'lon': float,
            'vulnerable_count': int,
            'svi_score': float
        }
    }
    """
    
    print("📊 Loading CDC SVI County Data...")
    
    # Load SVI data
    svi = pd.read_csv(filepath)
    
    print(f"   Loaded {len(svi)} counties")
    
    # Filter for high vulnerability (top 25% = RPL_THEMES >= 0.75)
    # RPL_THEMES is the overall SVI percentile ranking (0-1)
    vulnerable = svi[svi['RPL_THEMES'] >= 0.75].copy()
    
    print(f"   Found {len(vulnerable)} highly vulnerable counties (SVI ≥ 0.75)")
    
    # Create vulnerable populations dictionary
    vulnerable_pops = {}
    
    for idx, row in vulnerable.iterrows():
        # Get county and state
        county = row['COUNTY']
        state = row['STATE']
        
        # Get vulnerability metrics
        svi_score = row['RPL_THEMES']
        total_pop = row.get('E_TOTPOP', 0)
        
        # Estimate vulnerable population (top quartile of SVI)
        # Use elderly (65+) + below poverty + minority as proxy
        vulnerable_count = int(
            row.get('E_AGE65', 0) + 
            row.get('E_POV150', 0) * 0.5 +  # 50% weight for poverty
            row.get('E_MINRTY', 0) * 0.3    # 30% weight for minority status
        )
        
        # Skip if no lat/lon
        if pd.isna(row.get('LAT')) or pd.isna(row.get('LON')):
            continue
        
        location_key = f"{county}, {state}"
        
        vulnerable_pops[location_key] = {
            'lat': float(row['LAT']),
            'lon': float(row['LON']),
            'vulnerable_count': max(vulnerable_count, 100),  # Minimum 100
            'svi_score': float(svi_score),
            'total_population': int(total_pop),
            'fips': row['FIPS']
        }
    
    print(f"   ✅ Created {len(vulnerable_pops)} vulnerable location profiles")
    
    return vulnerable_pops


def get_top_vulnerable_locations(n=100):
    """
    Get top N most vulnerable locations for focused monitoring
    
    Returns top 100 counties by SVI score for dashboard
    """
    
    all_locations = load_cdc_svi_data()
    
    # Convert to DataFrame for sorting
    df = pd.DataFrame.from_dict(all_locations, orient='index')
    df['location_name'] = df.index
    
    # Sort by SVI score (highest vulnerability first)
    df = df.sort_values('svi_score', ascending=False).head(n)
    
    # Convert back to dictionary
    top_locations = {}
    for idx, row in df.iterrows():
        top_locations[row['location_name']] = {
            'lat': row['lat'],
            'lon': row['lon'],
            'vulnerable_count': row['vulnerable_count'],
            'svi_score': row['svi_score']
        }
    
    print(f"\n📍 Top {n} Most Vulnerable Locations:")
    print(df[['location_name', 'vulnerable_count', 'svi_score']].head(10))
    
    return top_locations


def save_vulnerable_populations(filepath='vulnerable_populations.json'):
    """
    Save vulnerable populations to JSON file for easy loading
    """
    
    locations = load_cdc_svi_data()
    
    with open(filepath, 'w') as f:
        json.dump(locations, f, indent=2)
    
    print(f"\n💾 Saved {len(locations)} locations to {filepath}")
    
    return filepath


if __name__ == "__main__":
    
    print("=" * 70)
    print("CDC SVI VULNERABLE POPULATIONS LOADER")
    print("=" * 70)
    
    # Load all vulnerable counties
    all_locations = load_cdc_svi_data()
    
    print(f"\n📊 Summary Statistics:")
    df = pd.DataFrame.from_dict(all_locations, orient='index')
    print(f"   Total vulnerable locations: {len(df)}")
    print(f"   Total vulnerable individuals: {df['vulnerable_count'].sum():,}")
    print(f"   Average SVI score: {df['svi_score'].mean():.3f}")
    print(f"   States covered: {df.index.str.split(',').str[1].str.strip().nunique()}")
    
    # Save to JSON
    save_vulnerable_populations()
    
    # Show top 20 most vulnerable
    print("\n🔥 Top 20 Most Vulnerable Locations:")
    top = df.nlargest(20, 'svi_score')[['vulnerable_count', 'svi_score', 'total_population']]
    print(top.to_string())
    
    print("\n" + "=" * 70)
    print("✅ Ready to use in dashboard!")
    print("=" * 70)