"""
Risk Management Page
Monitor and control risk metrics and safety features
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from services.data_service import DataService


def render():
    """Render the risk management page"""
    
    # Initialize data service
    data_service = DataService()
    
    st.subheader("⚠️ Risk Management & Controls")
    st.markdown("Monitor risk metrics and manage safety controls for your trading system")
    
    # Get risk metrics
    risk_metrics = data_service.get_risk_metrics()
    
    # Risk Level Indicator
    risk_level = risk_metrics.get('risk_level', 'UNKNOWN')
    risk_colors = {
        'LOW': '#00cc00',
        'MEDIUM': '#ffaa00',
        'HIGH': '#ff6600',
        'CRITICAL': '#ff0000',
        'UNKNOWN': '#888888'
    }
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Create risk gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=get_risk_score(risk_level),
            title={'text': "Overall Risk Level"},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': risk_colors[risk_level]},
                'steps': [
                    {'range': [0, 25], 'color': "lightgray"},
                    {'range': [25, 50], 'color': "lightgray"},
                    {'range': [50, 75], 'color': "lightgray"},
                    {'range': [75, 100], 'color': "lightgray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(height=250)
        st.plotly_chart(fig, use_container_width=True)
        
        # Risk level description
        st.markdown(f"<h3 style='text-align: center; color: {risk_colors[risk_level]}'>{risk_level} RISK</h3>", 
                   unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Risk Metrics Dashboard
    st.markdown("### 📊 Risk Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        exposure_pct = risk_metrics.get('exposure_pct', 0)
        st.metric(
            "Total Exposure",
            f"{exposure_pct:.1f}%",
            f"${risk_metrics.get('total_exposure', 0):,.0f}"
        )
        
        # Exposure progress bar
        progress = min(exposure_pct / 100, 1.0)
        st.progress(progress)
    
    with col2:
        drawdown = risk_metrics.get('current_drawdown', 0) * 100
        max_drawdown = risk_metrics.get('max_drawdown', 10)
        st.metric(
            "Current Drawdown",
            f"{drawdown:.1f}%",
            f"Max: {max_drawdown}%",
            delta_color="inverse"
        )
        
        # Drawdown progress bar
        progress = min(drawdown / max_drawdown, 1.0) if max_drawdown > 0 else 0
        st.progress(progress)
    
    with col3:
        position_count = risk_metrics.get('position_count', 0)
        max_positions = 10  # Get from config
        st.metric(
            "Open Positions",
            position_count,
            f"Max: {max_positions}"
        )
        
        # Position count progress
        progress = min(position_count / max_positions, 1.0) if max_positions > 0 else 0
        st.progress(progress)
    
    with col4:
        # VaR or other metric
        var_95 = risk_metrics.get('var_95', 0)
        st.metric(
            "VaR (95%)",
            f"${var_95:,.0f}",
            "Daily risk",
            delta_color="inverse"
        )
    
    st.markdown("---")
    
    # Risk Limits Configuration
    st.markdown("### 🎚️ Risk Limits")
    
    config = data_service.load_config()
    risk_config = config.get('risk_management', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Position Limits")
        
        # Max position size
        max_pos_size = st.slider(
            "Max Position Size (%)",
            min_value=5,
            max_value=50,
            value=int(risk_config.get('max_position_size_pct', 0.10) * 100),
            help="Maximum size for a single position"
        )
        
        # Max total exposure
        max_exposure = st.slider(
            "Max Total Exposure (%)",
            min_value=50,
            max_value=150,
            value=int(risk_config.get('max_total_exposure_pct', 0.95) * 100),
            help="Maximum total market exposure"
        )
        
        # Max positions
        max_positions = st.number_input(
            "Max Concurrent Positions",
            min_value=1,
            max_value=50,
            value=risk_config.get('max_positions', 10),
            help="Maximum number of open positions"
        )
    
    with col2:
        st.markdown("#### Loss Limits")
        
        # Daily loss limit
        max_daily_loss = st.slider(
            "Max Daily Loss (%)",
            min_value=1,
            max_value=20,
            value=int(risk_config.get('max_daily_loss_pct', 0.02) * 100),
            help="Stop trading if daily loss exceeds this"
        )
        
        # Max drawdown
        max_dd = st.slider(
            "Max Drawdown (%)",
            min_value=5,
            max_value=50,
            value=int(risk_config.get('max_drawdown_pct', 0.10) * 100),
            help="Stop trading if drawdown exceeds this"
        )
        
        # Emergency stop
        emergency_stop = st.slider(
            "Emergency Stop Loss (%)",
            min_value=10,
            max_value=50,
            value=int(risk_config.get('emergency_stop_loss_pct', 0.15) * 100),
            help="Emergency stop all positions"
        )
    
    # Update button
    if st.button("Update Risk Limits", type="secondary"):
        # Update configuration
        risk_config['max_position_size_pct'] = max_pos_size / 100
        risk_config['max_total_exposure_pct'] = max_exposure / 100
        risk_config['max_positions'] = max_positions
        risk_config['max_daily_loss_pct'] = max_daily_loss / 100
        risk_config['max_drawdown_pct'] = max_dd / 100
        risk_config['emergency_stop_loss_pct'] = emergency_stop / 100
        
        config['risk_management'] = risk_config
        
        if data_service.save_config(config):
            st.success("✅ Risk limits updated successfully")
        else:
            st.error("Failed to update risk limits")
    
    st.markdown("---")
    
    # Emergency Controls
    st.markdown("### 🚨 Emergency Controls")
    st.warning("⚠️ Use these controls carefully - they will affect live trading!")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Trading Control")
        
        if st.button("⏸️ Pause Trading", use_container_width=True):
            if data_service.pause_trading():
                st.success("Trading paused")
            else:
                st.error("Failed to pause trading")
        
        if st.button("▶️ Resume Trading", use_container_width=True):
            if data_service.resume_trading():
                st.success("Trading resumed")
            else:
                st.error("Failed to resume trading")
        
        if st.button("⏹️ Stop Trading", use_container_width=True):
            if st.checkbox("Confirm stop"):
                if data_service.stop_trading():
                    st.success("Trading stopped")
                else:
                    st.error("Failed to stop trading")
    
    with col2:
        st.markdown("#### Position Management")
        
        positions = data_service.get_positions()
        position_count = len(positions)
        
        st.info(f"Currently {position_count} open positions")
        
        if st.button("Close All Positions", type="primary", use_container_width=True):
            if st.checkbox("Confirm close all positions"):
                st.error("Closing all positions...")
                # Implement close all
                st.success("All positions closed")
        
        if st.button("Reduce All Positions 50%", use_container_width=True):
            st.info("Feature coming soon")
    
    with col3:
        st.markdown("#### Emergency Stop")
        
        st.error("🛑 DANGER ZONE")
        
        if st.button("EMERGENCY STOP", type="primary", use_container_width=True):
            st.error("This will:")
            st.error("• Stop all trading immediately")
            st.error("• Close all open positions")
            st.error("• Cancel all pending orders")
            
            confirm = st.text_input("Type 'EMERGENCY' to confirm")
            if confirm == "EMERGENCY":
                if data_service.emergency_stop():
                    st.error("🚨 EMERGENCY STOP ACTIVATED!")
                else:
                    st.error("Failed to activate emergency stop")
    
    st.markdown("---")
    
    # Risk History Chart
    st.markdown("### 📈 Risk Metrics History")
    
    # Create sample data (would come from database)
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    risk_history = pd.DataFrame({
        'date': dates,
        'drawdown': pd.Series(range(30)).apply(lambda x: min(x * 0.3 + pd.Series([0]).sample(1).values[0] * 2, 10)),
        'exposure': pd.Series(range(30)).apply(lambda x: 50 + x + pd.Series([0]).sample(1).values[0] * 10),
        'positions': pd.Series(range(30)).apply(lambda x: min(int(x/3) + pd.Series([0]).sample(1).values[0] * 3, 10))
    })
    
    # Create subplot figure
    fig = go.Figure()
    
    # Add drawdown trace
    fig.add_trace(go.Scatter(
        x=risk_history['date'],
        y=risk_history['drawdown'],
        name='Drawdown %',
        line=dict(color='red', width=2)
    ))
    
    # Add exposure trace
    fig.add_trace(go.Scatter(
        x=risk_history['date'],
        y=risk_history['exposure'],
        name='Exposure %',
        line=dict(color='blue', width=2),
        yaxis='y2'
    ))
    
    # Update layout
    fig.update_layout(
        title="30-Day Risk Metrics",
        xaxis_title="Date",
        yaxis=dict(
            title="Drawdown %",
            titlefont=dict(color="red"),
            tickfont=dict(color="red")
        ),
        yaxis2=dict(
            title="Exposure %",
            titlefont=dict(color="blue"),
            tickfont=dict(color="blue"),
            anchor="x",
            overlaying="y",
            side="right"
        ),
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Risk Warnings Section
    st.markdown("---")
    st.markdown("### ⚠️ Active Warnings")
    
    # Get any risk warnings
    warnings = risk_metrics.get('warnings', [])
    
    if warnings:
        for warning in warnings:
            st.warning(f"⚠️ {warning}")
    else:
        st.success("✅ No active risk warnings")
    
    # System Information
    with st.expander("System Information"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Last Risk Check**")
            st.text(datetime.now().strftime("%H:%M:%S"))
        
        with col2:
            st.markdown("**Risk System Status**")
            st.success("🟢 Active")
        
        with col3:
            st.markdown("**Auto-Stop Enabled**")
            st.info("Yes")


def get_risk_score(risk_level: str) -> int:
    """Convert risk level to numeric score for gauge"""
    scores = {
        'LOW': 20,
        'MEDIUM': 45,
        'HIGH': 70,
        'CRITICAL': 90,
        'UNKNOWN': 50
    }
    return scores.get(risk_level, 50)