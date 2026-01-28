"""
Real-Time Fire Data Integration
Connects to NASA FIRMS, NIFC, and CAL FIRE APIs for live wildfire data
"""

import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from datetime import datetime, timedelta
import json
import time

class FireDataIntegrator:
    """
    Fetches and processes real-time wildfire data from multiple sources
    """
    
    def __init__(self):
        # NASA FIRMS API (requires free API key from https://firms.modaps.eosdis.nasa.gov/api/)
        self.firms_base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        
        # CAL FIRE (public data)
        self.calfire_url = "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Fire_Perimeters/FeatureServer/0/query"
        
        # NIFC (National Interagency Fire Center)
        self.nifc_url = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/Current_WildlandFire_Perimeters/FeatureServer/0/query"
    
    def get_firms_active_fires(self, area_bounds, api_key, days=1):
        """
        Get active fire detections from NASA FIRMS
        
        Args:
            area_bounds: (west, south, east, north) tuple
            api_key: Your FIRMS API key
            days: Number of days back to fetch (1-10)
        
        Returns:
            GeoDataFrame of active fire points
        """
        west, south, east, north = area_bounds
        
        url = f"{self.firms_base_url}{api_key}/VIIRS_NOAA20_NRT/{west},{south},{east},{north}/{days}"
        
        try:
            df = pd.read_csv(url)
            
            # Convert to GeoDataFrame
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
            
            # Add useful derived fields
            gdf['detection_time'] = pd.to_datetime(gdf['acq_date'] + ' ' + gdf['acq_time'])
            gdf['confidence_level'] = pd.cut(gdf['confidence'], 
                                            bins=[0, 30, 60, 100],
                                            labels=['Low', 'Moderate', 'High'])
            
            return gdf
            
        except Exception as e:
            print(f"Error fetching FIRMS data: {e}")
            return None
    
    def get_calfire_perimeters(self):
        """
        Get current fire perimeters from CAL FIRE
        
        Returns:
            GeoDataFrame of fire perimeters
        """
        params = {
            'where': "1=1",  # Get all active fires
            'outFields': "*",
            'f': 'geojson',
            'returnGeometry': 'true'
        }
        
        try:
            response = requests.get(self.calfire_url, params=params)
            data = response.json()
            
            gdf = gpd.GeoDataFrame.from_features(data['features'], crs='EPSG:4326')
            
            # Clean and process
            if 'FIRE_NAME' in gdf.columns:
                gdf['fire_name'] = gdf['FIRE_NAME']
            if 'GIS_ACRES' in gdf.columns:
                gdf['acres'] = gdf['GIS_ACRES']
            if 'DATE_CUR' in gdf.columns:
                gdf['last_updated'] = pd.to_datetime(gdf['DATE_CUR'])
            
            return gdf
            
        except Exception as e:
            print(f"Error fetching CAL FIRE data: {e}")
            return None
    
    def get_nifc_perimeters(self):
        """
        Get national fire perimeters from NIFC
        
        Returns:
            GeoDataFrame of fire perimeters
        """
        params = {
            'where': "1=1",
            'outFields': "*",
            'f': 'geojson',
            'returnGeometry': 'true'
        }
        
        try:
            response = requests.get(self.nifc_url, params=params, timeout=30)
            data = response.json()
            
            gdf = gpd.GeoDataFrame.from_features(data['features'], crs='EPSG:4326')
            
            return gdf
            
        except Exception as e:
            print(f"Error fetching NIFC data: {e}")
            return None
    
    def calculate_proximity_to_fires(self, vulnerable_locations_gdf, fire_perimeters_gdf):
        """
        Calculate distance from vulnerable populations to active fires
        
        Args:
            vulnerable_locations_gdf: GeoDataFrame with vulnerable population points
            fire_perimeters_gdf: GeoDataFrame with fire perimeters
        
        Returns:
            GeoDataFrame with distance calculations
        """
        # Ensure same CRS
        if vulnerable_locations_gdf.crs != fire_perimeters_gdf.crs:
            fire_perimeters_gdf = fire_perimeters_gdf.to_crs(vulnerable_locations_gdf.crs)
        
        # Calculate distance to nearest fire
        vulnerable_locations_gdf['distance_to_fire_km'] = vulnerable_locations_gdf.geometry.apply(
            lambda point: fire_perimeters_gdf.geometry.distance(point).min() * 111  # Convert degrees to km
        )
        
        # Flag locations within various distances
        vulnerable_locations_gdf['within_5km'] = vulnerable_locations_gdf['distance_to_fire_km'] <= 5
        vulnerable_locations_gdf['within_10km'] = vulnerable_locations_gdf['distance_to_fire_km'] <= 10
        vulnerable_locations_gdf['within_25km'] = vulnerable_locations_gdf['distance_to_fire_km'] <= 25
        
        return vulnerable_locations_gdf
    
    def generate_evacuation_zones(self, fire_perimeters_gdf, buffer_distances=[5, 10, 25]):
        """
        Create evacuation zone buffers around fire perimeters
        
        Args:
            fire_perimeters_gdf: GeoDataFrame with fire perimeters
            buffer_distances: List of buffer distances in km
        
        Returns:
            Dict of GeoDataFrames for each evacuation zone
        """
        # Convert to projected CRS for accurate buffering (meters)
        fire_projected = fire_perimeters_gdf.to_crs('EPSG:3857')
        
        evacuation_zones = {}
        
        for distance_km in buffer_distances:
            buffer_m = distance_km * 1000
            buffered = fire_projected.copy()
            buffered['geometry'] = fire_projected.geometry.buffer(buffer_m)
            
            # Convert back to WGS84
            buffered = buffered.to_crs('EPSG:4326')
            
            evacuation_zones[f'{distance_km}km'] = buffered
        
        return evacuation_zones
    
    def identify_at_risk_populations(self, vulnerable_gdf, evacuation_zones):
        """
        Identify which vulnerable individuals fall within evacuation zones
        
        Args:
            vulnerable_gdf: GeoDataFrame of vulnerable population locations
            evacuation_zones: Dict of evacuation zone GeoDataFrames
        
        Returns:
            GeoDataFrame with risk zone assignments
        """
        vulnerable_gdf['risk_zone'] = 'Safe'
        
        # Check each evacuation zone (from outer to inner for proper assignment)
        for zone_name in reversed(sorted(evacuation_zones.keys())):
            zone_gdf = evacuation_zones[zone_name]
            
            # Spatial join to find points within this zone
            within_zone = gpd.sjoin(vulnerable_gdf, zone_gdf, how='inner', predicate='within')
            
            # Update risk zone for these individuals
            vulnerable_gdf.loc[within_zone.index, 'risk_zone'] = zone_name
        
        # Assign urgency levels
        zone_to_urgency = {
            '5km': 'IMMEDIATE',
            '10km': 'HIGH',
            '25km': 'MODERATE',
            'Safe': 'LOW'
        }
        
        vulnerable_gdf['urgency'] = vulnerable_gdf['risk_zone'].map(zone_to_urgency)
        
        return vulnerable_gdf
    
    def export_for_caregiver_alerts(self, at_risk_gdf, output_path):
        """
        Export list of at-risk individuals for caregiver notification system
        
        Args:
            at_risk_gdf: GeoDataFrame with risk assessments
            output_path: Where to save the alert list
        """
        # Filter to only those needing alerts
        needs_alert = at_risk_gdf[at_risk_gdf['urgency'].isin(['IMMEDIATE', 'HIGH', 'MODERATE'])]
        
        # Create alert dataframe
        alerts = needs_alert[['individual_id', 'caregiver_contact', 'urgency', 
                             'risk_zone', 'distance_to_fire_km']].copy()
        
        alerts['alert_sent'] = False
        alerts['timestamp'] = datetime.now()
        
        # Sort by urgency
        urgency_order = {'IMMEDIATE': 0, 'HIGH': 1, 'MODERATE': 2}
        alerts['urgency_rank'] = alerts['urgency'].map(urgency_order)
        alerts = alerts.sort_values('urgency_rank')
        
        alerts.to_csv(output_path, index=False)
        print(f"Alert list generated: {len(alerts)} caregivers to notify")
        
        return alerts


# Example usage
if __name__ == "__main__":
    print("Fire Data Integration Module")
    print("=" * 60)
    
    integrator = FireDataIntegrator()
    
    # Example: Get CAL FIRE perimeters
    print("\nFetching CAL FIRE perimeter data...")
    calfire_gdf = integrator.get_calfire_perimeters()
    
    if calfire_gdf is not None:
        print(f"Retrieved {len(calfire_gdf)} active fire perimeters")
        print(calfire_gdf[['fire_name', 'acres']].head())
    
    # Example: Create evacuation zones
    if calfire_gdf is not None and len(calfire_gdf) > 0:
        print("\nGenerating evacuation zones...")
        evac_zones = integrator.generate_evacuation_zones(calfire_gdf)
        print(f"Created zones: {list(evac_zones.keys())}")
    
    print("\n" + "=" * 60)
    print("Integration module ready for deployment!")
    print("\nNext steps:")
    print("1. Get NASA FIRMS API key (free): https://firms.modaps.eosdis.nasa.gov/api/")
    print("2. Load your vulnerable population dataset")
    print("3. Run proximity analysis")
    print("4. Generate caregiver alerts")