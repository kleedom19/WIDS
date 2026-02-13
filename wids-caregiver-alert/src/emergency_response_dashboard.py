"""
emergency_response_dashboard.py

Team Coordination & Resource Management for Emergency Personnel

Features:
- Team roster with availability status
- Resource inventory (water, equipment, vehicles)
- Deployment assignments based on fire characteristics
- Caregiver contact status monitoring
- Real-time incident command view

Author: 49ers Intelligence Lab
Date: 2025-02-11
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import folium
from streamlit_folium import st_folium


def render_emergency_response_dashboard(fire_data):
    """Main emergency response coordination dashboard"""
    
    st.title("🚒 Emergency Response Command Center")
    st.markdown("Real-time team coordination and resource deployment")
    
    # Initialize session state for roster data
    if 'team_roster' not in st.session_state:
        st.session_state.team_roster = initialize_default_roster()
    if 'resource_inventory' not in st.session_state:
        st.session_state.resource_inventory = initialize_default_resources()
    if 'caregiver_contacts' not in st.session_state:
        st.session_state.caregiver_contacts = {}
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    available_personnel = sum(1 for p in st.session_state.team_roster 
                             if p['status'] == 'Available')
    col1.metric("Available Personnel", 
               f"{available_personnel}/{len(st.session_state.team_roster)}")
    
    active_fires = len(fire_data) if fire_data is not None and len(fire_data) > 0 else 0
    col2.metric("Active Incidents", active_fires)
    
    deployed_teams = sum(1 for p in st.session_state.team_roster 
                        if p['status'] == 'Deployed')
    col3.metric("Deployed Teams", deployed_teams)
    
    contacted_families = sum(1 for status in st.session_state.caregiver_contacts.values() 
                            if status == 'Contacted')
    col4.metric("Families Contacted", 
               f"{contacted_families}/{len(st.session_state.caregiver_contacts)}")
    
    # Tab navigation
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Team Roster", 
        "📦 Resource Inventory", 
        "🎯 Deployment Assignments",
        "📞 Caregiver Contact Status"
    ])
    
    with tab1:
        render_team_roster()
    
    with tab2:
        render_resource_inventory()
    
    with tab3:
        render_deployment_assignments(fire_data)
    
    with tab4:
        render_caregiver_contacts()


def initialize_default_roster():
    """Default team roster - can be imported from CSV"""
    return [
        {'id': 1, 'name': 'Captain Rodriguez', 'role': 'Incident Commander', 
         'specialization': 'Wildfire Management', 'status': 'Available', 
         'certifications': 'Type 1 IC, NWCG'},
        {'id': 2, 'name': 'Lt. Chen', 'role': 'Engine Captain', 
         'specialization': 'Structure Protection', 'status': 'Available',
         'certifications': 'Type 3 Engine Boss'},
        {'id': 3, 'name': 'Firefighter Martinez', 'role': 'Wildland FF', 
         'specialization': 'Hand Crew', 'status': 'Deployed',
         'certifications': 'FFT1, S-190'},
        {'id': 4, 'name': 'Engineer Thompson', 'role': 'Equipment Operator', 
         'specialization': 'Water Supply', 'status': 'Available',
         'certifications': 'Type 1 Pump Operator'},
        {'id': 5, 'name': 'Paramedic Johnson', 'role': 'EMS Lead', 
         'specialization': 'Medical Support', 'status': 'Available',
         'certifications': 'Paramedic, TCCC'},
        {'id': 6, 'name': 'Lt. Patel', 'role': 'Division Supervisor', 
         'specialization': 'Tactical Planning', 'status': 'Deployed',
         'certifications': 'DIVS, S-420'},
        {'id': 7, 'name': 'Firefighter Davis', 'role': 'Wildland FF', 
         'specialization': 'Hand Crew', 'status': 'Available',
         'certifications': 'FFT2, S-190'},
        {'id': 8, 'name': 'Captain Brown', 'role': 'Air Operations', 
         'specialization': 'Helicopter Coordination', 'status': 'Available',
         'certifications': 'ATGS, Helicopter Manager'},
    ]


def initialize_default_resources():
    """Default resource inventory"""
    return {
        'Water Supply': {
            'Type 1 Engine (500 gal)': {'available': 3, 'deployed': 1, 'maintenance': 0},
            'Type 3 Engine (300 gal)': {'available': 5, 'deployed': 2, 'maintenance': 1},
            'Water Tender (2000 gal)': {'available': 2, 'deployed': 1, 'maintenance': 0},
            'Portable Tanks': {'available': 12, 'deployed': 4, 'maintenance': 0},
        },
        'Equipment': {
            'Chainsaws': {'available': 8, 'deployed': 3, 'maintenance': 1},
            'Drip Torches': {'available': 15, 'deployed': 5, 'maintenance': 0},
            'Pulaskis': {'available': 20, 'deployed': 8, 'maintenance': 2},
            'Portable Pumps': {'available': 6, 'deployed': 2, 'maintenance': 0},
            'Radios (Handheld)': {'available': 25, 'deployed': 10, 'maintenance': 2},
        },
        'Vehicles': {
            'Crew Carriers': {'available': 4, 'deployed': 2, 'maintenance': 0},
            'Command Vehicles': {'available': 2, 'deployed': 1, 'maintenance': 0},
            'Bulldozers': {'available': 2, 'deployed': 1, 'maintenance': 0},
        },
        'Safety Gear': {
            'Fire Shelters': {'available': 30, 'deployed': 12, 'maintenance': 0},
            'Nomex Jackets': {'available': 25, 'deployed': 10, 'maintenance': 3},
            'Hard Hats': {'available': 30, 'deployed': 12, 'maintenance': 0},
        }
    }


def render_team_roster():
    """Team roster management interface"""
    
    st.subheader("Team Roster & Availability")
    
    # Add new personnel button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ Add Personnel", use_container_width=True):
            st.session_state.show_add_personnel = True
    
    # Display roster
    roster_df = pd.DataFrame(st.session_state.team_roster)
    
    # Status color coding
    def status_color(status):
        colors = {
            'Available': '🟢',
            'Deployed': '🔴',
            'Off-Duty': '⚫',
            'Training': '🟡'
        }
        return colors.get(status, '⚪')
    
    roster_df['Status Icon'] = roster_df['status'].apply(status_color)
    
    # Display table
    display_cols = ['Status Icon', 'name', 'role', 'specialization', 'certifications', 'status']
    st.dataframe(
        roster_df[display_cols],
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # Quick stats
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    status_counts = roster_df['status'].value_counts()
    col1.metric("Available", status_counts.get('Available', 0))
    col2.metric("Deployed", status_counts.get('Deployed', 0))
    col3.metric("Off-Duty", status_counts.get('Off-Duty', 0))
    
    # Update status form
    with st.expander("Update Personnel Status"):
        selected_person = st.selectbox(
            "Select Personnel",
            options=roster_df['name'].tolist()
        )
        
        new_status = st.selectbox(
            "New Status",
            options=['Available', 'Deployed', 'Off-Duty', 'Training']
        )
        
        if st.button("Update Status"):
            for person in st.session_state.team_roster:
                if person['name'] == selected_person:
                    person['status'] = new_status
            st.success(f"Updated {selected_person} to {new_status}")
            st.rerun()


def render_resource_inventory():
    """Resource inventory tracking"""
    
    st.subheader("Resource Inventory & Allocation")
    
    resources = st.session_state.resource_inventory
    
    # Summary metrics
    total_available = sum(
        item['available'] 
        for category in resources.values() 
        for item in category.values()
    )
    total_deployed = sum(
        item['deployed'] 
        for category in resources.values() 
        for item in category.values()
    )
    total_maintenance = sum(
        item['maintenance'] 
        for category in resources.values() 
        for item in category.values()
    )
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Available", total_available)
    col2.metric("Deployed", total_deployed)
    col3.metric("In Maintenance", total_maintenance)
    col4.metric("Deployment Rate", f"{total_deployed/(total_available+total_deployed)*100:.0f}%")
    
    # Resource breakdown by category
    for category, items in resources.items():
        with st.expander(f"📦 {category}", expanded=(category == 'Water Supply')):
            
            # Create dataframe for this category
            cat_data = []
            for item_name, counts in items.items():
                cat_data.append({
                    'Resource': item_name,
                    'Available': counts['available'],
                    'Deployed': counts['deployed'],
                    'Maintenance': counts['maintenance'],
                    'Total': counts['available'] + counts['deployed'] + counts['maintenance']
                })
            
            cat_df = pd.DataFrame(cat_data)
            
            # Display table
            st.dataframe(cat_df, use_container_width=True, hide_index=True)
            
            # Visualization
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Available', x=cat_df['Resource'], y=cat_df['Available'], marker_color='green'))
            fig.add_trace(go.Bar(name='Deployed', x=cat_df['Resource'], y=cat_df['Deployed'], marker_color='red'))
            fig.add_trace(go.Bar(name='Maintenance', x=cat_df['Resource'], y=cat_df['Maintenance'], marker_color='orange'))
            
            fig.update_layout(
                barmode='stack',
                height=300,
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)


def render_deployment_assignments(fire_data):
    """AI-powered deployment recommendations based on fire characteristics"""
    
    st.subheader("Deployment Assignments")
    
    if fire_data is None or len(fire_data) == 0:
        st.info("No active fires requiring deployment")
        return
    
    st.markdown("""
    **Automated resource matching** based on:
    - Fire size & growth rate
    - Terrain & accessibility
    - Proximity to structures
    - Team specializations
    - Resource availability
    """)
    
    # Generate assignments for each major fire
    assignments = []
    
    for idx, fire in fire_data.head(10).iterrows():
        fire_name = fire.get('fire_name', 'Unknown Fire')
        acres = fire.get('acres', 0)
        containment = fire.get('containment', 0)
        
        # Determine needed resources based on fire size
        if acres > 1000:
            priority = "CRITICAL"
            teams_needed = ["Type 1 IC", "Division Supervisor", "Air Operations"]
            resources_needed = ["Type 1 Engine (500 gal)", "Water Tender (2000 gal)", "Bulldozers"]
        elif acres > 100:
            priority = "HIGH"
            teams_needed = ["Engine Captain", "Wildland FF"]
            resources_needed = ["Type 3 Engine (300 gal)", "Portable Pumps"]
        else:
            priority = "MEDIUM"
            teams_needed = ["Wildland FF"]
            resources_needed = ["Type 3 Engine (300 gal)"]
        
        assignments.append({
            'Fire': fire_name,
            'Size (acres)': acres if acres and acres == acres else 0,
            'Containment': f"{containment:.0f}%" if containment and containment == containment else "0%",
            'Priority': priority,
            'Teams Needed': ', '.join(teams_needed),
            'Resources Needed': ', '.join(resources_needed[:2])
        })
    
    # Display assignments
    assignments_df = pd.DataFrame(assignments)
    
    # Priority color coding
    def priority_color(priority):
        colors = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}
        return colors.get(priority, '⚪')
    
    assignments_df['Priority Icon'] = assignments_df['Priority'].apply(priority_color)
    
    st.dataframe(
        assignments_df[['Priority Icon', 'Fire', 'Size (acres)', 'Containment', 'Teams Needed', 'Resources Needed']],
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # Assignment actions
    st.markdown("---")
    st.subheader("Deploy Team")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_fire = st.selectbox(
            "Incident",
            options=assignments_df['Fire'].tolist()
        )
    
    with col2:
        available_personnel = [p['name'] for p in st.session_state.team_roster 
                              if p['status'] == 'Available']
        selected_personnel = st.multiselect(
            "Assign Personnel",
            options=available_personnel
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Deploy Team", type="primary", use_container_width=True):
            if selected_personnel:
                for person_name in selected_personnel:
                    for person in st.session_state.team_roster:
                        if person['name'] == person_name:
                            person['status'] = 'Deployed'
                st.success(f"Deployed {len(selected_personnel)} personnel to {selected_fire}")
                st.rerun()
            else:
                st.warning("Select personnel to deploy")


def render_caregiver_contacts():
    """Track which caregivers have confirmed contact with their families"""
    
    st.subheader("Caregiver Contact Confirmation")
    
    st.markdown("""
    **Purpose:** Track which vulnerable individuals have been successfully contacted by their caregivers.  
    This helps emergency responders prioritize door-to-door notifications.
    """)
    
    # Sample vulnerable population data
    if not st.session_state.caregiver_contacts:
        st.session_state.caregiver_contacts = {
            'Maria Garcia (82, Mobility Limited)': 'Contacted',
            'John Lee (75, Medical Equipment)': 'Contacted',
            'Sarah Johnson (68, Lives Alone)': 'Not Contacted',
            'Robert Williams (71, No Vehicle)': 'Contacted',
            'Linda Martinez (79, Hearing Impaired)': 'Not Contacted',
            'James Davis (73, Cognitive Impairment)': 'In Progress',
        }
    
    # Stats
    col1, col2, col3 = st.columns(3)
    
    total = len(st.session_state.caregiver_contacts)
    contacted = sum(1 for s in st.session_state.caregiver_contacts.values() if s == 'Contacted')
    not_contacted = sum(1 for s in st.session_state.caregiver_contacts.values() if s == 'Not Contacted')
    
    col1.metric("Total Vulnerable", total)
    col2.metric("Contacted", contacted, delta=f"{contacted/total*100:.0f}%")
    col3.metric("Needs Contact", not_contacted, delta=f"-{not_contacted}", delta_color="inverse")
    
    # Contact list
    st.markdown("---")
    
    contact_data = []
    for name, status in st.session_state.caregiver_contacts.items():
        contact_data.append({
            'Individual': name,
            'Status': status,
            'Status Icon': '✅' if status == 'Contacted' else ('🔄' if status == 'In Progress' else '❌')
        })
    
    contact_df = pd.DataFrame(contact_data)
    
    # Filter
    filter_status = st.radio(
        "Filter by status",
        options=['All', 'Not Contacted', 'In Progress', 'Contacted'],
        horizontal=True
    )
    
    if filter_status != 'All':
        contact_df = contact_df[contact_df['Status'] == filter_status]
    
    st.dataframe(
        contact_df[['Status Icon', 'Individual', 'Status']],
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # Update status
    st.markdown("---")
    with st.expander("Update Contact Status"):
        update_name = st.selectbox(
            "Select Individual",
            options=list(st.session_state.caregiver_contacts.keys())
        )
        
        new_status = st.radio(
            "New Status",
            options=['Not Contacted', 'In Progress', 'Contacted'],
            horizontal=True
        )
        
        if st.button("Update"):
            st.session_state.caregiver_contacts[update_name] = new_status
            st.success(f"Updated {update_name} to {new_status}")
            st.rerun()


if __name__ == "__main__":
    st.set_page_config(page_title="Emergency Response Dashboard", layout="wide")
    render_emergency_response_dashboard(None)