"""
Trading Bot Dashboard
Main Streamlit application for monitoring and controlling the trading system
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Page configuration
st.set_page_config(
    page_title="Trading Bot Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .success-metric {
        color: #00cc00;
    }
    .danger-metric {
        color: #ff4444;
    }
    .warning-metric {
        color: #ffaa00;
    }
    div[data-testid="stSidebar"] {
        background-color: #262730;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Live Monitoring'

# Sidebar navigation
st.sidebar.title("🤖 Trading Bot Control")
st.sidebar.markdown("---")

# Navigation menu
pages = {
    "📊 Live Monitoring": "pages.live_monitoring",
    "🚀 Deploy Strategy": "pages.deploy_strategy", 
    "⚠️ Risk Management": "pages.risk_management",
    "📈 Performance History": "pages.performance_history"
}

# Page selection
selected_page = st.sidebar.radio(
    "Navigation",
    list(pages.keys()),
    index=0
)

# System status in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("System Status")

# Import data service
try:
    from services.data_service import DataService
    data_service = DataService()
    
    # Get system status
    status = data_service.get_system_status()
    
    if status:
        if status.get('trading_enabled'):
            st.sidebar.success("🟢 Trading Active")
        else:
            st.sidebar.error("🔴 Trading Stopped")
        
        st.sidebar.metric("Capital", f"${status.get('current_capital', 0):,.2f}")
        st.sidebar.metric("Open Positions", status.get('position_count', 0))
        
        # Show current strategy
        active_strategy = status.get('active_strategy', 'None')
        st.sidebar.info(f"Strategy: {active_strategy}")
    else:
        st.sidebar.warning("⚠️ Cannot connect to trading system")
        
except Exception as e:
    st.sidebar.error(f"System offline: {str(e)}")

# Emergency controls in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Emergency Controls")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("⏸️ Pause", use_container_width=True):
        try:
            data_service.pause_trading()
            st.sidebar.success("Trading paused")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")

with col2:
    if st.button("🛑 STOP", type="primary", use_container_width=True):
        if st.sidebar.checkbox("Confirm emergency stop"):
            try:
                data_service.emergency_stop()
                st.sidebar.error("Emergency stop activated!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Failed: {e}")

# Main content area
st.title(f"{selected_page}")
st.markdown("---")

# Dynamic page loading
try:
    if selected_page == "📊 Live Monitoring":
        from pages import live_monitoring
        live_monitoring.render()
    elif selected_page == "🚀 Deploy Strategy":
        from pages import deploy_strategy
        deploy_strategy.render()
    elif selected_page == "⚠️ Risk Management":
        from pages import risk_management
        risk_management.render()
    elif selected_page == "📈 Performance History":
        from pages import performance_history
        performance_history.render()
except ImportError as e:
    st.error(f"Page not yet implemented: {e}")
    st.info("This feature is coming soon!")
except Exception as e:
    st.error(f"Error loading page: {e}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888;'>
        Trading Bot Dashboard v1.0 | 
        <a href='#' style='color: #888;'>Documentation</a> | 
        <a href='#' style='color: #888;'>Settings</a>
    </div>
    """,
    unsafe_allow_html=True
)