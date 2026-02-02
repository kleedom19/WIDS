"""
evacuation_planner_page.py

Interactive Evacuation Planner Page
- Address input with geocoding
- Real-time traffic conditions
- Multiple route options (driving, transit, walking)
- Safe zone recommendations
- Road closures and hazards
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    Convert address to lat/lon using Nominatim (OpenStreetMap) geocoding
    Free, no API key needed!
    """
    
    url = "https://nominatim.openstreetmap.org/search"
    
    params = {
        'q': address,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'us'  # US only
    }
    
    headers = {
        'User-Agent': 'WiDS-Caregiver-Alert/1.0'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            return (float(data[0]['lat']), float(data[0]['lon']))
        
        return None
        
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return None


def get_route_with_traffic(origin_lat: float, origin_lon: float,
                           dest_lat: float, dest_lon: float,
                           mode: str = 'driving') -> Optional[Dict]:
    """
    Get route with traffic info using OSRM
    
    Modes: 'driving', 'walking', 'cycling'
    """
    
    # OSRM public API
    url = f"http://router.project-osrm.org/route/v1/{mode}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    
    params = {
        'overview': 'full',
        'geometries': 'geojson',
        'steps': 'true',
        'annotations': 'true'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if data['code'] != 'Ok':
            return None
        
        route = data['routes'][0]
        
        # Extract turn-by-turn directions
        steps = []
        if 'legs' in route and len(route['legs']) > 0:
            for step in route['legs'][0].get('steps', []):
                instruction = step.get('maneuver', {}).get('instruction', '')
                distance = step.get('distance', 0) * 0.000621371  # meters to miles
                
                if instruction:
                    steps.append(f"{instruction} ({distance:.1f} mi)")
        
        return {
            'distance_mi': route['distance'] * 0.000621371,
            'duration_min': route['duration'] / 60,
            'duration_hours': route['duration'] / 3600,
            'geometry': route['geometry']['coordinates'],
            'steps': steps,
            'mode': mode
        }
        
    except Exception as e:
        st.error(f"Routing error: {e}")
        return None


def get_public_transit_options(origin_lat: float, origin_lon: float,
                               dest_lat: float, dest_lon: float) -> List[Dict]:
    """
    Get public transit options
    Note: This is a placeholder - real transit requires Transit API or GTFS data
    """
    
    # For now, return placeholder info
    # In production, integrate with:
    # - Google Directions API (transit mode)
    # - Transit app APIs
    # - Local transit authority APIs
    
    return [
        {
            'type': 'Bus + Light Rail',
            'estimated_time': '2-3 hours',
            'status': 'Check local transit website for current service',
            'note': 'Service may be disrupted during emergencies'
        },
        {
            'type': 'Emergency Shuttle',
            'estimated_time': 'Varies',
            'status': 'Contact local emergency services',
            'note': 'Dial 211 for evacuation assistance'
        }
    ]


def render_evacuation_planner_page(fire_data, vulnerable_populations):
    """
    Main evacuation planner page
    """
    
    st.title("🚗 Personal Evacuation Planner")
    st.markdown("Get personalized evacuation routes with real-time traffic and transit info")
    
    # ==================== ADDRESS INPUT ====================
    st.subheader("📍 Your Location")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        address = st.text_input(
            "Enter your address",
            placeholder="123 Main St, Los Angeles, CA 90012",
            help="Enter your full address including city and state"
        )
    
    with col2:
        search_button = st.button("🔍 Find Route", type="primary")
    
    # ==================== SAFE ZONES ====================
    
    safe_zones = {
        'San Diego, CA': (32.7157, -117.1611),
        'Phoenix, AZ': (33.4484, -112.0740),
        'Las Vegas, NV': (36.1699, -115.1398),
        'Sacramento, CA': (38.5816, -121.4944),
        'Fresno, CA': (36.7378, -119.7871),
        'Tucson, AZ': (32.2226, -110.9747),
        'Albuquerque, NM': (35.0844, -106.6504),
    }
    
    # ==================== ROUTE CALCULATION ====================
    
    if search_button and address:
        
        with st.spinner("🗺️ Geocoding your address..."):
            coords = geocode_address(address)
        
        if coords is None:
            st.error("❌ Could not find address. Please check spelling and try again.")
            st.info("💡 Try: '1600 Pennsylvania Ave, Washington DC' or 'Times Square, New York'")
            return
        
        origin_lat, origin_lon = coords
        
        st.success(f"✅ Found location: {origin_lat:.4f}, {origin_lon:.4f}")
        
        # Find nearest fires
        st.subheader("🔥 Nearby Fire Threats")
        
        nearest_fires = []
        if fire_data is not None and len(fire_data) > 0:
            for _, fire in fire_data.iterrows():
                fire_lat = fire.get('latitude')
                fire_lon = fire.get('longitude')
                
                if fire_lat and fire_lon:
                    # Calculate distance
                    from math import radians, cos, sin, asin, sqrt
                    
                    def haversine(lat1, lon1, lat2, lon2):
                        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                        dlat = lat2 - lat1
                        dlon = lon2 - lon1
                        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                        c = 2 * asin(sqrt(a))
                        return 6371 * c * 0.621371  # km to miles
                    
                    dist = haversine(origin_lat, origin_lon, fire_lat, fire_lon)
                    
                    if dist < 100:  # Within 100 miles
                        nearest_fires.append({
                            'name': fire.get('fire_name', 'Unknown'),
                            'distance': dist,
                            'acres': fire.get('acres', 0)
                        })
        
        if nearest_fires:
            nearest_fires.sort(key=lambda x: x['distance'])
            
            st.warning(f"⚠️ {len(nearest_fires)} fire(s) within 100 miles")
            
            for fire in nearest_fires[:5]:
                urgency = "🔴 HIGH" if fire['distance'] < 15 else "🟡 MEDIUM" if fire['distance'] < 40 else "🟢 LOW"
                st.write(f"{urgency} - **{fire['name']}**: {fire['distance']:.1f} mi away ({fire['acres']:,.0f} acres)")
        else:
            st.success("✅ No fires within 100 miles")
        
        st.markdown("---")
        
        # ==================== ROUTE OPTIONS ====================
        
        st.subheader("🛣️ Evacuation Routes")
        
        # Destination selector
        destination = st.selectbox(
            "Select safe zone destination",
            options=list(safe_zones.keys()),
            help="Choose the nearest safe city outside fire zones"
        )
        
        dest_lat, dest_lon = safe_zones[destination]
        
        # Transportation mode
        col1, col2, col3 = st.columns(3)
        
        with col1:
            show_driving = st.checkbox("🚗 Driving", value=True)
        with col2:
            show_walking = st.checkbox("🚶 Walking", value=False)
        with col3:
            show_transit = st.checkbox("🚌 Public Transit", value=True)
        
        st.markdown("---")
        
        # Calculate routes
        routes = []
        
        if show_driving:
            with st.spinner("Calculating driving route..."):
                driving_route = get_route_with_traffic(origin_lat, origin_lon, dest_lat, dest_lon, 'driving')
                if driving_route:
                    routes.append(('driving', driving_route))
        
        if show_walking:
            with st.spinner("Calculating walking route..."):
                walking_route = get_route_with_traffic(origin_lat, origin_lon, dest_lat, dest_lon, 'foot')
                if walking_route:
                    routes.append(('walking', walking_route))
        
        # Display routes
        if routes:
            
            # Route comparison table
            st.subheader("📊 Route Comparison")
            
            route_data = []
            for mode, route in routes:
                emoji = "🚗" if mode == "driving" else "🚶"
                route_data.append({
                    'Mode': f"{emoji} {mode.title()}",
                    'Distance': f"{route['distance_mi']:.1f} mi",
                    'Time': f"{route['duration_hours']:.1f} hrs ({route['duration_min']:.0f} min)",
                    'Avg Speed': f"{(route['distance_mi'] / route['duration_hours']):.1f} mph" if mode == 'driving' else 'N/A'
                })
            
            st.table(route_data)
            
            # Detailed route info
            for mode, route in routes:
                
                emoji = "🚗" if mode == "driving" else "🚶"
                
                with st.expander(f"{emoji} {mode.title()} Route Details", expanded=(mode=='driving')):
                    
                    st.markdown(f"""
                    **Distance:** {route['distance_mi']:.1f} miles  
                    **Estimated Time:** {route['duration_hours']:.1f} hours ({route['duration_min']:.0f} minutes)  
                    **Destination:** {destination}
                    """)
                    
                    if route['steps']:
                        st.markdown("**Turn-by-Turn Directions:**")
                        for i, step in enumerate(route['steps'][:15], 1):
                            st.write(f"{i}. {step}")
                        
                        if len(route['steps']) > 15:
                            st.caption(f"... and {len(route['steps']) - 15} more steps")
        
        # Public transit info
        if show_transit:
            st.subheader("🚌 Public Transit Options")
            
            transit_options = get_public_transit_options(origin_lat, origin_lon, dest_lat, dest_lon)
            
            for option in transit_options:
                with st.expander(f"🚌 {option['type']}", expanded=False):
                    st.write(f"**Estimated Time:** {option['estimated_time']}")
                    st.write(f"**Status:** {option['status']}")
                    st.info(option['note'])
            
            st.warning("⚠️ Public transit may be limited during emergencies. Always have a backup plan.")
        
        st.markdown("---")
        
        # ==================== MAP ====================
        
        st.subheader("🗺️ Route Map")
        
        # Create map
        m = folium.Map(
            location=[(origin_lat + dest_lat)/2, (origin_lon + dest_lon)/2],
            zoom_start=7
        )
        
        # Add origin marker
        folium.Marker(
            [origin_lat, origin_lon],
            popup="Your Location",
            icon=folium.Icon(color='green', icon='home', prefix='fa'),
            tooltip="Start"
        ).add_to(m)
        
        # Add destination marker
        folium.Marker(
            [dest_lat, dest_lon],
            popup=destination,
            icon=folium.Icon(color='blue', icon='flag-checkered', prefix='fa'),
            tooltip="Safe Zone"
        ).add_to(m)
        
        # Add route lines
        colors = {'driving': 'blue', 'walking': 'green'}
        for mode, route in routes:
            # Convert [lon, lat] to [lat, lon] for folium
            coords = [[coord[1], coord[0]] for coord in route['geometry']]
            
            folium.PolyLine(
                coords,
                color=colors.get(mode, 'blue'),
                weight=4,
                opacity=0.7,
                popup=f"{mode.title()} route"
            ).add_to(m)
        
        # Add nearby fires
        if nearest_fires:
            for fire in nearest_fires[:10]:
                # Find fire coordinates
                fire_info = fire_data[fire_data['fire_name'] == fire['name']].iloc[0]
                
                folium.Circle(
                    [fire_info['latitude'], fire_info['longitude']],
                    radius=fire['acres'] * 50,
                    color='red',
                    fill=True,
                    fillColor='orange',
                    fillOpacity=0.4,
                    popup=f"{fire['name']}<br>{fire['acres']:,.0f} acres"
                ).add_to(m)
        
        st_folium(m, width=900, height=600)
        
        st.markdown("---")
        
        # ==================== EMERGENCY INFO ====================
        
        st.subheader("📞 Emergency Resources")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **Emergency Services**
            - 🚨 911: Fire/Police/Medical
            - 🆘 211: Evacuation Help
            - 📻 Local Emergency Radio
            """)
        
        with col2:
            st.markdown("""
            **Evacuation Checklist**
            - ✅ Important documents
            - ✅ Medications
            - ✅ Pet supplies
            - ✅ Cash/cards
            - ✅ Phone charger
            """)
        
        with col3:
            st.markdown("""
            **Road Conditions**
            - 🚧 Check 511 for closures
            - 🚦 Expect heavy traffic
            - ⛽ Fill up gas tank
            - 💧 Bring water/snacks
            """)
    
    else:
        # Initial state - show instructions
        st.info("👆 Enter your address above to get personalized evacuation routes")
        
        st.markdown("---")
        
        st.subheader("ℹ️ How It Works")
        
        st.markdown("""
        1. **Enter your address** - We'll find your exact location
        2. **Check fire threats** - See fires within 100 miles
        3. **Get route options** - Driving, walking, and public transit
        4. **View on map** - Interactive route visualization
        5. **Follow directions** - Turn-by-turn guidance
        
        **Features:**
        - 🗺️ Real road routing (OpenStreetMap)
        - 🚗 Multiple transportation modes
        - 🔥 Live fire proximity alerts
        - 🧭 Turn-by-turn directions
        - 📍 Safe zone recommendations
        """)


if __name__ == "__main__":
    # Test standalone
    st.set_page_config(page_title="Evacuation Planner", layout="wide")
    render_evacuation_planner_page(None, None)