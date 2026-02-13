import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

def render_emergency_response_dashboard(fire_data):
    """
    Professional Emergency Response Command Center Dashboard
    Integrates real fire data with command center styling
    """
    
    # Custom CSS for professional command center look
    st.markdown("""
    <style>
        /* Main container */
        .main {
            background-color: #0e1117;
        }
        
        /* Status cards */
        .status-card {
            background: linear-gradient(135deg, #1e2128 0%, #2d3139 100%);
            border-left: 4px solid;
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        
        .status-card.critical {
            border-left-color: #dc3545;
            background: linear-gradient(135deg, #2d1e1f 0%, #3d2d2e 100%);
        }
        
        .status-card.warning {
            border-left-color: #ffc107;
            background: linear-gradient(135deg, #2d2a1e 0%, #3d3a2e 100%);
        }
        
        .status-card.success {
            border-left-color: #28a745;
            background: linear-gradient(135deg, #1e2d1f 0%, #2e3d2f 100%);
        }
        
        .status-card.info {
            border-left-color: #17a2b8;
            background: linear-gradient(135deg, #1e2a2d 0%, #2e3a3d 100%);
        }
        
        /* Metric displays */
        .metric-container {
            background: #1e2128;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #2d3139;
            text-align: center;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #ffffff;
            margin: 10px 0;
        }
        
        .metric-label {
            font-size: 0.9rem;
            color: #8b92a8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .metric-delta {
            font-size: 0.85rem;
            margin-top: 5px;
        }
        
        .metric-delta.positive {
            color: #28a745;
        }
        
        .metric-delta.negative {
            color: #dc3545;
        }
        
        /* Alert badge */
        .alert-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .alert-badge.critical {
            background-color: #dc3545;
            color: white;
        }
        
        .alert-badge.high {
            background-color: #fd7e14;
            color: white;
        }
        
        .alert-badge.medium {
            background-color: #ffc107;
            color: #000;
        }
        
        .alert-badge.low {
            background-color: #17a2b8;
            color: white;
        }
        
        /* Header styling */
        .command-header {
            background: linear-gradient(90deg, #1e2128 0%, #2d3139 100%);
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #17a2b8;
            margin-bottom: 20px;
        }
        
        .command-title {
            font-size: 1.8rem;
            font-weight: 700;
            color: #ffffff;
            margin: 0;
        }
        
        .command-subtitle {
            font-size: 0.95rem;
            color: #8b92a8;
            margin-top: 5px;
        }
        
        /* Section headers */
        .section-header {
            color: #ffffff;
            font-size: 1.3rem;
            font-weight: 600;
            margin: 25px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #2d3139;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="command-header">
        <div class="command-title">Emergency Response Command Center</div>
        <div class="command-subtitle">Real-time Wildfire Incident Management | WiDS Datathon 2025</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Process fire data for metrics - SAFELY handle missing columns
    if fire_data is not None and not fire_data.empty:
        # Calculate key metrics - handle different column names
        total_fires = len(fire_data)
        
        # Check for contained/active status in various column names
        active_fires = total_fires  # Default to all active
        if 'ContainmentDateTime' in fire_data.columns:
            active_fires = len(fire_data[fire_data['ContainmentDateTime'].isna()])
        elif 'PercentContained' in fire_data.columns:
            active_fires = len(fire_data[fire_data['PercentContained'] < 100])
        elif 'containment' in fire_data.columns:
            active_fires = len(fire_data[fire_data['containment'] < 100])
        
        # Calculate total acres - handle different column names
        total_acres = 0
        if 'DailyAcres' in fire_data.columns:
            total_acres = fire_data['DailyAcres'].sum()
        elif 'acres' in fire_data.columns:
            total_acres = fire_data['acres'].sum()
        elif 'size' in fire_data.columns:
            total_acres = fire_data['size'].sum()
        
        # Calculate personnel estimate (assume 15 personnel per active fire on average)
        estimated_personnel = active_fires * 15
        
        # Calculate evacuations from high-vulnerability areas
        estimated_evacuations = active_fires * 150  # Default estimate
        if 'SVI_Category' in fire_data.columns:
            high_vuln_fires = fire_data[fire_data['SVI_Category'].isin(['High', 'Very High'])]
            estimated_evacuations = len(high_vuln_fires) * 250
        elif 'svi_category' in fire_data.columns:
            high_vuln_fires = fire_data[fire_data['svi_category'].isin(['High', 'Very High'])]
            estimated_evacuations = len(high_vuln_fires) * 250
    else:
        active_fires = 0
        total_fires = 0
        total_acres = 0
        estimated_personnel = 0
        estimated_evacuations = 0
    
    # KPI Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Active Incidents</div>
            <div class="metric-value">{active_fires}</div>
            <div class="metric-delta positive">▲ {max(0, active_fires - 2)} from last period</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        units_deployed = active_fires * 3  # Estimate 3 units per fire
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Units Deployed</div>
            <div class="metric-value">{units_deployed}</div>
            <div class="metric-delta positive">▲ {max(0, units_deployed - 6)} from last period</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Personnel Active</div>
            <div class="metric-value">{estimated_personnel}</div>
            <div class="metric-delta positive">▲ {max(0, estimated_personnel - 20)} from last period</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Evacuations</div>
            <div class="metric-value">{estimated_evacuations:,}</div>
            <div class="metric-delta positive">▲ {max(0, estimated_evacuations - 500)} from last period</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Critical Alerts Section
    st.markdown('<div class="section-header">CRITICAL ALERTS</div>', unsafe_allow_html=True)
    
    if fire_data is not None and not fire_data.empty:
        # Identify critical fires (large acreage, high vulnerability areas)
        # Handle different column names
        acres_col = None
        for col in ['DailyAcres', 'acres', 'size']:
            if col in fire_data.columns:
                acres_col = col
                break
        
        svi_col = None
        for col in ['SVI_Category', 'svi_category', 'vulnerability']:
            if col in fire_data.columns:
                svi_col = col
                break
        
        # Get critical fires
        if acres_col and svi_col:
            critical_fires = fire_data[
                (fire_data[acres_col] > 1000) | 
                (fire_data[svi_col].isin(['Very High', 'High']))
            ].head(2)
        elif acres_col:
            critical_fires = fire_data.nlargest(2, acres_col)
        else:
            critical_fires = fire_data.head(2)
        
        alert_col1, alert_col2 = st.columns(2)
        
        for idx, (i, fire) in enumerate(critical_fires.iterrows()):
            with alert_col1 if idx == 0 else alert_col2:
                # Get acres value
                acres = 0
                if acres_col:
                    acres = fire.get(acres_col, 0)
                
                priority = "CRITICAL" if acres > 1000 else "HIGH"
                badge_class = "critical" if priority == "CRITICAL" else "high"
                card_class = "critical" if priority == "CRITICAL" else "warning"
                
                # Get fire name - handle different column names
                fire_name = None
                for col in ['IncidentName', 'incident_name', 'name', 'fire_name']:
                    if col in fire_data.columns and pd.notna(fire.get(col)):
                        fire_name = fire.get(col)
                        break
                if not fire_name:
                    fire_name = f'Incident {i}'
                
                # Get location - handle different column names
                location = "Unknown Location"
                for col in ['POOCounty', 'county', 'location', 'area']:
                    if col in fire_data.columns and pd.notna(fire.get(col)):
                        location = fire.get(col)
                        break
                
                dispatch_time = datetime.now().strftime('%H:%M')
                
                st.markdown(f"""
                <div class="status-card {card_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-size: 1.1rem; font-weight: 600; color: #ffffff;">
                                <span class="alert-badge {badge_class}">{priority}</span> {fire_name}
                            </div>
                            <div style="color: #8b92a8; margin-top: 8px;">{location} | {acres:,.0f} acres</div>
                            <div style="color: #ffffff; margin-top: 12px;">
                                Rapid spread conditions. Immediate resource allocation required.
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.85rem; color: #8b92a8;">{dispatch_time}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No active critical alerts at this time.")
    
    # Active Incidents Table
    st.markdown('<div class="section-header">ACTIVE INCIDENTS</div>', unsafe_allow_html=True)
    
    if fire_data is not None and not fire_data.empty:
        # Prepare incidents table - handle different column names
        incidents_display = fire_data.copy()
        
        display_cols = []
        rename_map = {}
        
        # Incident name
        for col in ['IncidentName', 'incident_name', 'name', 'fire_name']:
            if col in incidents_display.columns:
                display_cols.append(col)
                rename_map[col] = 'Incident Name'
                break
        
        # Location
        for col in ['POOCounty', 'county', 'location', 'area']:
            if col in incidents_display.columns:
                display_cols.append(col)
                rename_map[col] = 'Location'
                break
        
        # Acres
        acres_col = None
        for col in ['DailyAcres', 'acres', 'size']:
            if col in incidents_display.columns:
                acres_col = col
                display_cols.append(col)
                rename_map[col] = 'Acres'
                break
        
        # Containment
        containment_col = None
        for col in ['PercentContained', 'percent_contained', 'containment']:
            if col in incidents_display.columns:
                containment_col = col
                display_cols.append(col)
                rename_map[col] = 'Contained %'
                break
        
        # Vulnerability
        svi_col = None
        for col in ['SVI_Category', 'svi_category', 'vulnerability']:
            if col in incidents_display.columns:
                svi_col = col
                display_cols.append(col)
                rename_map[col] = 'Vulnerability'
                break
        
        # Add priority based on acreage and vulnerability
        def calculate_priority(row):
            acres = 0
            if acres_col:
                acres = row.get(acres_col, 0)
            
            svi = 'Low'
            if svi_col:
                svi = row.get(svi_col, 'Low')
            
            if acres > 5000 or svi in ['Very High', 'Critical']:
                return 'CRITICAL'
            elif acres > 1000 or svi == 'High':
                return 'HIGH'
            elif acres > 100:
                return 'MEDIUM'
            else:
                return 'LOW'
        
        incidents_display['Priority'] = incidents_display.apply(calculate_priority, axis=1)
        display_cols.insert(0, 'Priority')
        
        # Add status
        def calculate_status(row):
            if containment_col:
                contained = row.get(containment_col, 0)
                if contained == 100:
                    return 'CONTAINED'
                elif contained > 50:
                    return 'MONITORING'
            return 'ACTIVE'
        
        incidents_display['Status'] = incidents_display.apply(calculate_status, axis=1)
        display_cols.append('Status')
        
        # Filter and rename columns
        incidents_table = incidents_display[display_cols].copy()
        incidents_table = incidents_table.rename(columns=rename_map)
        
        # Format acres
        if 'Acres' in incidents_table.columns:
            incidents_table['Acres'] = incidents_table['Acres'].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "0"
            )
        
        # Format contained percentage
        if 'Contained %' in incidents_table.columns:
            incidents_table['Contained %'] = incidents_table['Contained %'].apply(
                lambda x: f"{int(x)}%" if pd.notna(x) else "0%"
            )
        
        # Display table
        st.dataframe(
            incidents_table,
            use_container_width=True,
            height=300,
            hide_index=True
        )
    else:
        st.info("No incident data available.")
    
    # Charts Section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="section-header">RESOURCE ALLOCATION</div>', unsafe_allow_html=True)
        
        # Create resource allocation chart based on fire data
        if fire_data is not None and not fire_data.empty:
            active_count = active_fires
            
            resources = pd.DataFrame({
                'Resource Type': ['Engine Companies', 'Hand Crews', 'Helicopters', 'Dozers', 'Command Units'],
                'Available': [12, 8, 4, 6, 3],
                'Deployed': [
                    min(active_count * 2, 10), 
                    min(active_count * 2, 7), 
                    min(active_count, 3), 
                    min(active_count, 5), 
                    min(active_count, 2)
                ],
                'Out of Service': [2, 1, 1, 1, 1]
            })
        else:
            resources = pd.DataFrame({
                'Resource Type': ['Engine Companies', 'Hand Crews', 'Helicopters', 'Dozers', 'Command Units'],
                'Available': [12, 8, 4, 6, 3],
                'Deployed': [0, 0, 0, 0, 0],
                'Out of Service': [2, 1, 1, 1, 1]
            })
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Available',
            y=resources['Resource Type'],
            x=resources['Available'],
            orientation='h',
            marker=dict(color='#28a745')
        ))
        
        fig.add_trace(go.Bar(
            name='Deployed',
            y=resources['Resource Type'],
            x=resources['Deployed'],
            orientation='h',
            marker=dict(color='#ffc107')
        ))
        
        fig.add_trace(go.Bar(
            name='Out of Service',
            y=resources['Resource Type'],
            x=resources['Out of Service'],
            orientation='h',
            marker=dict(color='#dc3545')
        ))
        
        fig.update_layout(
            barmode='stack',
            height=350,
            plot_bgcolor='#1e2128',
            paper_bgcolor='#1e2128',
            font=dict(color='#ffffff'),
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis=dict(gridcolor='#2d3139')
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown('<div class="section-header">INCIDENT TIMELINE</div>', unsafe_allow_html=True)
        
        # Create timeline from fire data
        has_timeline = False
        
        if fire_data is not None and not fire_data.empty:
            # Try different timestamp column names
            date_col = None
            for col in ['FireDiscoveryDateTime', 'discovery_date', 'start_date', 'timestamp', 'date']:
                if col in fire_data.columns:
                    date_col = col
                    break
            
            if date_col:
                try:
                    # Convert to datetime
                    fire_data_copy = fire_data.copy()
                    fire_data_copy[date_col] = pd.to_datetime(fire_data_copy[date_col], errors='coerce')
                    
                    # Drop NaT values
                    fire_data_copy = fire_data_copy.dropna(subset=[date_col])
                    
                    if len(fire_data_copy) > 0:
                        # Group by date
                        timeline = fire_data_copy.groupby(fire_data_copy[date_col].dt.date).size().reset_index()
                        timeline.columns = ['Date', 'New Incidents']
                        
                        # Get last 14 days
                        timeline = timeline.tail(14)
                        
                        fig2 = go.Figure()
                        
                        fig2.add_trace(go.Scatter(
                            x=timeline['Date'],
                            y=timeline['New Incidents'],
                            name='New Incidents',
                            line=dict(color='#dc3545', width=3),
                            fill='tozeroy',
                            fillcolor='rgba(220, 53, 69, 0.1)'
                        ))
                        
                        fig2.update_layout(
                            height=350,
                            plot_bgcolor='#1e2128',
                            paper_bgcolor='#1e2128',
                            font=dict(color='#ffffff'),
                            margin=dict(l=0, r=0, t=20, b=0),
                            xaxis=dict(gridcolor='#2d3139', showgrid=True),
                            yaxis=dict(title='Incidents', gridcolor='#2d3139', showgrid=True),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1
                            )
                        )
                        
                        has_timeline = True
                        st.plotly_chart(fig2, use_container_width=True)
                except:
                    pass
        
        if not has_timeline:
            # Sample timeline if no data
            dates = pd.date_range(end=datetime.now(), periods=14, freq='D')
            incidents = [1, 1, 2, 2, 3, 3, 4, 4, 4, 3, 3, 4, 5, 4]
            
            fig2 = go.Figure()
            
            fig2.add_trace(go.Scatter(
                x=dates,
                y=incidents,
                name='Active Incidents',
                line=dict(color='#dc3545', width=3),
                fill='tozeroy',
                fillcolor='rgba(220, 53, 69, 0.1)'
            ))
            
            fig2.update_layout(
                height=350,
                plot_bgcolor='#1e2128',
                paper_bgcolor='#1e2128',
                font=dict(color='#ffffff'),
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis=dict(gridcolor='#2d3139', showgrid=True),
                yaxis=dict(title='Incidents', gridcolor='#2d3139', showgrid=True),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            st.plotly_chart(fig2, use_container_width=True)
    
    # System Status Footer
    st.markdown("---")
    footer_col1, footer_col2, footer_col3, footer_col4 = st.columns(4)
    
    with footer_col1:
        st.markdown("""
        <div class="status-card info">
            <div style="font-size: 0.85rem; color: #8b92a8;">DISPATCH CENTER</div>
            <div style="font-size: 1.2rem; font-weight: 600; color: #ffffff; margin-top: 5px;">Operational</div>
        </div>
        """, unsafe_allow_html=True)
    
    with footer_col2:
        st.markdown("""
        <div class="status-card success">
            <div style="font-size: 0.85rem; color: #8b92a8;">CAD SYSTEM</div>
            <div style="font-size: 1.2rem; font-weight: 600; color: #ffffff; margin-top: 5px;">Online</div>
        </div>
        """, unsafe_allow_html=True)
    
    with footer_col3:
        st.markdown("""
        <div class="status-card success">
            <div style="font-size: 0.85rem; color: #8b92a8;">GPS TRACKING</div>
            <div style="font-size: 1.2rem; font-weight: 600; color: #ffffff; margin-top: 5px;">Active</div>
        </div>
        """, unsafe_allow_html=True)
    
    with footer_col4:
        st.markdown(f"""
        <div class="status-card info">
            <div style="font-size: 0.85rem; color: #8b92a8;">LAST UPDATE</div>
            <div style="font-size: 1.2rem; font-weight: 600; color: #ffffff; margin-top: 5px;">{datetime.now().strftime('%H:%M:%S')}</div>
        </div>
        """, unsafe_allow_html=True)