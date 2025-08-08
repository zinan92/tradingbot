"""
Live Monitoring Page
Real-time display of positions, PnL, and trading activity
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
from typing import Dict, List, Any

from services.data_service import DataService


def render():
    """Render the live monitoring page"""
    
    # Initialize data service
    data_service = DataService()
    
    # Auto-refresh toggle
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader("📊 Live Trading Monitor")
    with col2:
        auto_refresh = st.checkbox("Auto-refresh (5s)", value=True)
    with col3:
        if st.button("🔄 Refresh Now"):
            st.rerun()
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(5)
        st.rerun()
    
    # PnL Summary Section
    st.markdown("### 💰 P&L Summary")
    pnl_summary = data_service.get_pnl_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_pnl = pnl_summary.get('total_pnl', 0)
        delta_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric(
            "Total P&L",
            f"${total_pnl:,.2f}",
            f"{(total_pnl / 10000 * 100):.2f}%" if total_pnl != 0 else "0%",
            delta_color=delta_color
        )
    
    with col2:
        daily_pnl = pnl_summary.get('daily_pnl', 0)
        delta_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            "Daily P&L",
            f"${daily_pnl:,.2f}",
            f"{(daily_pnl / 10000 * 100):.2f}%" if daily_pnl != 0 else "0%",
            delta_color=delta_color
        )
    
    with col3:
        win_rate = pnl_summary.get('win_rate', 0)
        st.metric(
            "Win Rate",
            f"{win_rate:.1f}%",
            f"{pnl_summary.get('total_trades', 0)} trades"
        )
    
    with col4:
        st.metric(
            "Open Positions",
            pnl_summary.get('open_positions', 0),
            "Active"
        )
    
    # Divider
    st.markdown("---")
    
    # Split view: Positions and Chart
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        # Active Positions Section
        st.markdown("### 📈 Active Positions")
        
        positions = data_service.get_positions()
        
        if positions:
            # Convert to DataFrame for better display
            df_positions = pd.DataFrame(positions)
            
            # Format the dataframe
            if not df_positions.empty:
                # Select and reorder columns
                display_columns = [
                    'symbol', 'side', 'quantity', 'entry_price', 
                    'current_price', 'unrealized_pnl', 'pnl_pct'
                ]
                
                # Filter columns that exist
                display_columns = [col for col in display_columns if col in df_positions.columns]
                df_display = df_positions[display_columns].copy()
                
                # Format numerical columns
                if 'quantity' in df_display.columns:
                    df_display['quantity'] = df_display['quantity'].apply(lambda x: f"{x:.4f}")
                if 'entry_price' in df_display.columns:
                    df_display['entry_price'] = df_display['entry_price'].apply(lambda x: f"${x:.2f}")
                if 'current_price' in df_display.columns:
                    df_display['current_price'] = df_display['current_price'].apply(lambda x: f"${x:.2f}")
                if 'unrealized_pnl' in df_display.columns:
                    df_display['unrealized_pnl'] = df_display['unrealized_pnl'].apply(
                        lambda x: f"${x:.2f}" if x >= 0 else f"-${abs(x):.2f}"
                    )
                if 'pnl_pct' in df_display.columns:
                    df_display['pnl_pct'] = df_display['pnl_pct'].apply(lambda x: f"{x:.2f}%")
                
                # Rename columns for display
                column_names = {
                    'symbol': 'Symbol',
                    'side': 'Side',
                    'quantity': 'Quantity',
                    'entry_price': 'Entry',
                    'current_price': 'Current',
                    'unrealized_pnl': 'Unrealized P&L',
                    'pnl_pct': 'P&L %'
                }
                df_display.rename(columns=column_names, inplace=True)
                
                # Display table with color coding
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Side": st.column_config.TextColumn(
                            "Side",
                            help="Position direction"
                        ),
                        "Unrealized P&L": st.column_config.TextColumn(
                            "Unrealized P&L",
                            help="Current profit/loss"
                        ),
                    }
                )
                
                # Position actions
                st.markdown("#### Position Actions")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    selected_position = st.selectbox(
                        "Select position to close",
                        options=[f"{p['symbol']} ({p['side']})" for p in positions],
                        key="position_select"
                    )
                
                with col2:
                    if st.button("Close Position", type="secondary"):
                        if selected_position:
                            # Extract position ID (would need actual implementation)
                            st.warning(f"Close {selected_position} - Feature coming soon")
                
                with col3:
                    if st.button("Close All Positions", type="primary"):
                        if st.checkbox("Confirm close all"):
                            st.error("Closing all positions - Feature coming soon")
            else:
                st.info("No data to display in positions")
        else:
            st.info("No active positions")
    
    with col_right:
        # P&L Chart
        st.markdown("### 📉 P&L Performance")
        
        # Get historical data
        perf_data = data_service.get_performance_history(days=7)
        
        if not perf_data.empty:
            # Create cumulative P&L chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=perf_data['date'],
                y=perf_data['cumulative_pnl'],
                mode='lines+markers',
                name='Cumulative P&L',
                line=dict(color='#00cc00' if perf_data['cumulative_pnl'].iloc[-1] >= 0 else '#ff4444', width=2),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                title="7-Day Cumulative P&L",
                xaxis_title="Date",
                yaxis_title="P&L ($)",
                height=300,
                showlegend=False,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Win rate over time
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=perf_data['date'],
                y=perf_data['win_rate'],
                name='Win Rate',
                marker_color='lightblue'
            ))
            
            fig2.update_layout(
                title="Daily Win Rate %",
                xaxis_title="Date",
                yaxis_title="Win Rate (%)",
                height=250,
                showlegend=False
            )
            
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No historical data available")
    
    # Recent Trades Section
    st.markdown("---")
    st.markdown("### 📋 Recent Trades")
    
    trades = data_service.get_recent_trades(limit=20)
    
    if trades:
        df_trades = pd.DataFrame(trades)
        
        # Select display columns
        trade_columns = ['symbol', 'side', 'filled_quantity', 'filled_price', 'status', 'filled_at']
        trade_columns = [col for col in trade_columns if col in df_trades.columns]
        
        if trade_columns:
            df_trade_display = df_trades[trade_columns].copy()
            
            # Format columns
            if 'filled_quantity' in df_trade_display.columns:
                df_trade_display['filled_quantity'] = df_trade_display['filled_quantity'].apply(
                    lambda x: f"{x:.4f}" if x else "0"
                )
            if 'filled_price' in df_trade_display.columns:
                df_trade_display['filled_price'] = df_trade_display['filled_price'].apply(
                    lambda x: f"${x:.2f}" if x else "$0"
                )
            if 'filled_at' in df_trade_display.columns:
                df_trade_display['filled_at'] = pd.to_datetime(df_trade_display['filled_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Rename columns
            trade_column_names = {
                'symbol': 'Symbol',
                'side': 'Side',
                'filled_quantity': 'Quantity',
                'filled_price': 'Price',
                'status': 'Status',
                'filled_at': 'Time'
            }
            df_trade_display.rename(columns=trade_column_names, inplace=True)
            
            # Display trades
            st.dataframe(
                df_trade_display,
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No recent trades")
    
    # System Information Footer
    st.markdown("---")
    with st.expander("System Information"):
        system_status = data_service.get_system_status()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Trading Status**")
            if system_status.get('trading_enabled'):
                st.success("🟢 Active")
            else:
                st.error("🔴 Stopped")
        
        with col2:
            st.markdown("**Active Strategy**")
            st.info(system_status.get('active_strategy', 'None'))
        
        with col3:
            st.markdown("**Last Update**")
            st.text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))