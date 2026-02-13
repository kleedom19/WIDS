"""
landing_page.py — Secure Login with Role-Based Access

Authentication system for wildfire emergency response platform.
Credentials determine dashboard access:
- Emergency Response Personnel → Incident command features
- Evacuees & Caregivers → Evacuation planning
- Data Analysts → Research tools

Author: 49ers Intelligence Lab
Date: 2025-02-11
"""

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader


def render_landing_page():
    """Secure login page with role-based authentication"""
    
    # Custom CSS
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
        .login-box {
            max-width: 400px;
            margin: 2rem auto;
            padding: 2rem;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .info-box {
            background: #f0f2f6;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Hero section
    st.markdown("""
    <div class="hero-section">
        <h1>🔥 Wildfire Emergency Response Platform</h1>
        <p style="font-size: 1.2rem; margin-top: 1rem;">
            Secure access for emergency personnel, evacuees, and analysts
        </p>
        <p style="font-size: 0.9rem; opacity: 0.9;">
            56 territories | Real-time fire data | 2,847+ vulnerable counties
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Login configuration
    config = get_auth_config()
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    # Login widget
    try:
        # Newer versions return dict
        authenticator.login(location='main')
        
        # Access session state values
        authentication_status = st.session_state.get('authentication_status')
        name = st.session_state.get('name')
        username = st.session_state.get('username')
    except:
        # Fallback for older versions
        name, authentication_status, username = None, None, None
    
    if authentication_status:
        # Successfully authenticated
        authenticator.logout(location='sidebar')
        
        # Get user's role from config
        user_role = config['credentials']['usernames'][username]['role']
        st.session_state.user_role = user_role
        st.session_state.username = name
        
        # Welcome message
        role_emoji = {
            'emergency_response': '🚒',
            'evacuee_caregiver': '👨‍👩‍👧‍👦',
            'data_analyst': '📊'
        }
        
        st.success(f"Welcome, {name}! {role_emoji.get(user_role, '')}")
        
        # Redirect to appropriate dashboard
        st.rerun()
        
    elif authentication_status == False:
        st.error('Username/password is incorrect')
        show_demo_credentials()
        
    elif authentication_status == None:
        st.warning('Please enter your username and password')
        show_demo_credentials()


def get_auth_config():
    """
    Authentication configuration with demo accounts.
    
    In production, this would:
    - Read from secure database (Supabase, Firebase)
    - Integrate with agency CAD/RMS systems
    - Use CJIS-compliant authentication
    """
    
    # Hash passwords using bcrypt
    import bcrypt
    
    def hash_password(password):
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    config = {
        'credentials': {
            'usernames': {
                'fire_captain': {
                    'name': 'Captain Rodriguez',
                    'password': hash_password('emergency2025'),
                    'role': 'emergency_response',
                    'agency': 'CAL FIRE'
                },
                'incident_commander': {
                    'name': 'IC Thompson',
                    'password': hash_password('incident2025'),
                    'role': 'emergency_response',
                    'agency': 'USFS'
                },
                'caregiver1': {
                    'name': 'Maria Garcia',
                    'password': hash_password('evacuate2025'),
                    'role': 'evacuee_caregiver',
                    'agency': 'Public'
                },
                'caregiver2': {
                    'name': 'John Lee',
                    'password': hash_password('evacuate2025'),
                    'role': 'evacuee_caregiver',
                    'agency': 'Public'
                },
                'analyst1': {
                    'name': 'Dr. Sarah Chen',
                    'password': hash_password('research2025'),
                    'role': 'data_analyst',
                    'agency': 'UNC Charlotte'
                },
                'demo': {
                    'name': 'Demo User',
                    'password': hash_password('demo2025'),
                    'role': 'evacuee_caregiver',
                    'agency': 'Public'
                }
            }
        },
        'cookie': {
            'name': 'wildfire_auth_cookie',
            'key': 'wids_secret_key_2025',  # In production: use secure random key
            'expiry_days': 1
        }
    }
    
    return config


def show_demo_credentials():
    """Display demo credentials for testing"""
    
    with st.expander("🔓 Demo Credentials (For Testing Only)"):
        st.markdown("""
        ### Emergency Response Personnel
        - **Username:** `fire_captain` | **Password:** `emergency2025`
        - **Username:** `incident_commander` | **Password:** `incident2025`
        
        ### Evacuees & Caregivers
        - **Username:** `caregiver1` | **Password:** `evacuate2025`
        - **Username:** `demo` | **Password:** `demo2025`
        
        ### Data Analysts
        - **Username:** `analyst1` | **Password:** `research2025`
        
        ---
        
        **Security Note:** In production deployment, this platform would integrate with:
        - Agency CAD/RMS systems (Tyler, Motorola, Hexagon)
        - CJIS-compliant authentication
        - Multi-factor authentication (MFA)
        - Role-based access control (RBAC) via Active Directory
        
        Personnel data shown in dashboards is synthetic for demonstration purposes.
        """)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Wildfire Emergency Response Platform - Login",
        page_icon="🔥",
        layout="wide"
    )
    render_landing_page()