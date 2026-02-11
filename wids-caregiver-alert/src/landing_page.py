"""
landing_page.py — Multi-Role Landing Page

Directs users to appropriate dashboards:
- Emergency Response Personnel → Resource & Team Coordination
- Evacuees & Caregivers → Evacuation Planning & Alerts
- Data Analysts & Developers → Research & Analytics

Author: 49ers Intelligence Lab
Date: 2025-02-11
"""

import streamlit as st


def render_landing_page():
    """Main landing page with role selection"""
    
    st.markdown("""
    <style>
        .hero-section {
            text-align: center;
            padding: 2rem 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        .role-card {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            transition: all 0.3s ease;
            cursor: pointer;
            height: 100%;
        }
        .role-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
            transform: translateY(-2px);
        }
        .role-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .role-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #333;
            margin-bottom: 0.5rem;
        }
        .role-description {
            color: #666;
            margin-bottom: 1rem;
        }
        .feature-list {
            text-align: left;
            color: #555;
            font-size: 0.9rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Hero section
    st.markdown("""
    <div class="hero-section">
        <h1>🔥 Wildfire Emergency Response Platform</h1>
        <p style="font-size: 1.2rem; margin-top: 1rem;">
            Real-time coordination for emergency personnel, evacuees, and caregivers
        </p>
        <p style="font-size: 0.9rem; opacity: 0.9;">
            Covering all 50 states, DC, Puerto Rico, U.S. Virgin Islands, Guam, American Samoa, and Northern Mariana Islands
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### Select Your Role")
    
    col1, col2, col3 = st.columns(3)
    
    # Emergency Response Personnel
    with col1:
        st.markdown("""
        <div class="role-card">
            <div class="role-icon">🚒</div>
            <div class="role-title">Emergency Response</div>
            <div class="role-description">
                For firefighters, incident commanders, and emergency coordinators
            </div>
            <div class="feature-list">
                ✓ Team roster & resource management<br>
                ✓ Real-time deployment assignments<br>
                ✓ Equipment & water supply tracking<br>
                ✓ Contact status monitoring<br>
                ✓ Incident command dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚒 I'm Emergency Response Personnel", 
                    type="primary", 
                    use_container_width=True,
                    key="btn_emergency"):
            st.session_state.user_role = "emergency_response"
            st.rerun()
    
    # Evacuees & Caregivers
    with col2:
        st.markdown("""
        <div class="role-card">
            <div class="role-icon">👨‍👩‍👧‍👦</div>
            <div class="role-title">Evacuees & Caregivers</div>
            <div class="role-description">
                For individuals evacuating or caring for vulnerable family members
            </div>
            <div class="feature-list">
                ✓ Personalized evacuation alerts<br>
                ✓ Safe route planning & shelters<br>
                ✓ Family contact confirmation<br>
                ✓ Accessible transit options<br>
                ✓ Real-time fire proximity warnings
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("👨‍👩‍👧‍👦 I Need to Evacuate / Help Someone Evacuate", 
                    type="primary", 
                    use_container_width=True,
                    key="btn_evacuee"):
            st.session_state.user_role = "evacuee_caregiver"
            st.rerun()
    
    # Data Analysts & Developers
    with col3:
        st.markdown("""
        <div class="role-card">
            <div class="role-icon">📊</div>
            <div class="role-title">Research & Analytics</div>
            <div class="role-description">
                For data scientists, emergency planners, and policy analysts
            </div>
            <div class="feature-list">
                ✓ Evacuation delay analysis<br>
                ✓ Equity disparity metrics<br>
                ✓ Predictive risk modeling<br>
                ✓ Geographic vulnerability mapping<br>
                ✓ Historical fire pattern analysis
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📊 I'm a Data Analyst / Researcher", 
                    type="primary", 
                    use_container_width=True,
                    key="btn_analyst"):
            st.session_state.user_role = "data_analyst"
            st.rerun()
    
    # Platform info
    st.markdown("---")
    st.markdown("### Platform Capabilities")
    
    col_a, col_b, col_c, col_d = st.columns(4)
    
    col_a.metric("Coverage Area", "56 Territories", 
                help="All 50 states + DC + 5 U.S. territories")
    col_b.metric("Live Fire Data", "Real-time", 
                help="NASA FIRMS + NIFC + local agencies")
    col_c.metric("Vulnerable Counties", "2,847", 
                help="CDC Social Vulnerability Index ≥ 0.75")
    col_d.metric("Data Sources", "12+", 
                help="Federal, state, and territorial agencies")
    
    st.markdown("---")
    st.caption("""
    **Built by:** 49ers Intelligence Lab, UNC Charlotte  
    **For:** WiDS Datathon 2025  
    **Data:** NASA FIRMS, NIFC, CDC SVI, FEMA, State DOTs, Territorial Emergency Management  
    **License:** Open Source (Educational Use)
    """)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Wildfire Emergency Response Platform",
        page_icon="🔥",
        layout="wide"
    )
    render_landing_page()