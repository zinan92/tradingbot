"""
Performance History Page
Historical performance analysis and charts
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from services.data_service import DataService


def render():
    """Render the performance history page"""
    
    # Initialize data service
    data_service = DataService()
    
    st.subheader("📈 Performance History & Analytics")
    st.markdown("Analyze your trading performance over time")
    
    # Time period selector
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        period_options = {
            7: "Last 7 Days",
            30: "Last 30 Days",
            90: "Last 3 Months",
            365: "Last Year"
        }
        selected_period = st.selectbox(
            "Time Period",
            options=list(period_options.keys()),
            format_func=lambda x: period_options[x],
            index=1
        )
    
    with col2:
        chart_type = st.selectbox(
            "Chart Type",
            options=["Line", "Area", "Bar"],
            index=0
        )
    
    with col3:
        # Placeholder for additional filters
        st.markdown("")
    
    # Get performance data
    perf_data = data_service.get_performance_history(days=selected_period)
    
    if perf_data.empty:
        # Generate sample data for demonstration
        perf_data = generate_sample_performance_data(selected_period)
    
    # Performance Summary Cards
    st.markdown("### 📊 Performance Summary")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # Calculate metrics
    total_return = perf_data['cumulative_pnl'].iloc[-1] if not perf_data.empty else 0
    total_trades = perf_data['trades'].sum() if not perf_data.empty else 0
    avg_win_rate = perf_data['win_rate'].mean() if not perf_data.empty else 0
    best_day = perf_data['daily_pnl'].max() if not perf_data.empty else 0
    worst_day = perf_data['daily_pnl'].min() if not perf_data.empty else 0
    
    with col1:
        st.metric(
            "Total Return",
            f"${total_return:,.2f}",
            f"{(total_return / 10000 * 100):.2f}%" if total_return != 0 else "0%"
        )
    
    with col2:
        st.metric(
            "Total Trades",
            f"{total_trades:,.0f}",
            f"~{total_trades/selected_period:.0f}/day"
        )
    
    with col3:
        st.metric(
            "Avg Win Rate",
            f"{avg_win_rate:.1f}%",
            "Overall"
        )
    
    with col4:
        st.metric(
            "Best Day",
            f"${best_day:,.2f}",
            "P&L"
        )
    
    with col5:
        st.metric(
            "Worst Day",
            f"${worst_day:,.2f}",
            "P&L",
            delta_color="inverse"
        )
    
    st.markdown("---")
    
    # Main Performance Chart
    st.markdown("### 💹 Cumulative P&L Chart")
    
    if not perf_data.empty:
        fig = create_performance_chart(perf_data, chart_type)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No performance data available for the selected period")
    
    # Additional Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Daily P&L Distribution")
        if not perf_data.empty:
            fig = px.histogram(
                perf_data,
                x='daily_pnl',
                nbins=20,
                title="Daily P&L Distribution",
                labels={'daily_pnl': 'Daily P&L ($)', 'count': 'Frequency'},
                color_discrete_sequence=['#00cc00']
            )
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🎯 Win Rate Trend")
        if not perf_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=perf_data['date'],
                y=perf_data['win_rate'],
                mode='lines+markers',
                name='Win Rate',
                line=dict(color='purple', width=2),
                marker=dict(size=6)
            ))
            
            # Add average line
            avg_win_rate = perf_data['win_rate'].mean()
            fig.add_hline(
                y=avg_win_rate,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Avg: {avg_win_rate:.1f}%"
            )
            
            fig.update_layout(
                title="Win Rate Over Time",
                xaxis_title="Date",
                yaxis_title="Win Rate (%)",
                showlegend=False,
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Performance Metrics Table
    st.markdown("### 📋 Detailed Metrics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Returns Analysis")
        
        if not perf_data.empty:
            returns_metrics = calculate_returns_metrics(perf_data)
            
            metrics_df = pd.DataFrame([
                {"Metric": "Total Return", "Value": f"${returns_metrics['total_return']:,.2f}"},
                {"Metric": "Average Daily Return", "Value": f"${returns_metrics['avg_daily']:,.2f}"},
                {"Metric": "Best Day", "Value": f"${returns_metrics['best_day']:,.2f}"},
                {"Metric": "Worst Day", "Value": f"${returns_metrics['worst_day']:,.2f}"},
                {"Metric": "Positive Days", "Value": f"{returns_metrics['positive_days']}"},
                {"Metric": "Negative Days", "Value": f"{returns_metrics['negative_days']}"},
                {"Metric": "Max Consecutive Wins", "Value": f"{returns_metrics['max_consecutive_wins']}"},
                {"Metric": "Max Consecutive Losses", "Value": f"{returns_metrics['max_consecutive_losses']}"}
            ])
            
            st.dataframe(metrics_df, hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown("#### Risk Metrics")
        
        if not perf_data.empty:
            risk_metrics = calculate_risk_metrics(perf_data)
            
            risk_df = pd.DataFrame([
                {"Metric": "Sharpe Ratio", "Value": f"{risk_metrics['sharpe_ratio']:.2f}"},
                {"Metric": "Sortino Ratio", "Value": f"{risk_metrics['sortino_ratio']:.2f}"},
                {"Metric": "Max Drawdown", "Value": f"{risk_metrics['max_drawdown']:.2%}"},
                {"Metric": "Avg Drawdown", "Value": f"{risk_metrics['avg_drawdown']:.2%}"},
                {"Metric": "Volatility (Daily)", "Value": f"{risk_metrics['volatility']:.2%}"},
                {"Metric": "Downside Deviation", "Value": f"{risk_metrics['downside_deviation']:.2%}"},
                {"Metric": "Profit Factor", "Value": f"{risk_metrics['profit_factor']:.2f}"},
                {"Metric": "Recovery Factor", "Value": f"{risk_metrics['recovery_factor']:.2f}"}
            ])
            
            st.dataframe(risk_df, hide_index=True, use_container_width=True)
    
    st.markdown("---")
    
    # Monthly Performance Heatmap
    st.markdown("### 🗓️ Monthly Performance Heatmap")
    
    if not perf_data.empty and len(perf_data) > 30:
        monthly_data = create_monthly_heatmap_data(perf_data)
        
        fig = go.Figure(data=go.Heatmap(
            z=monthly_data['returns'],
            x=monthly_data['days'],
            y=monthly_data['months'],
            colorscale='RdYlGn',
            zmid=0,
            text=monthly_data['text'],
            texttemplate="%{text}",
            textfont={"size": 10},
            colorbar=dict(title="P&L ($)")
        ))
        
        fig.update_layout(
            title="Daily P&L Heatmap",
            xaxis_title="Day of Month",
            yaxis_title="Month",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Export Options
    st.markdown("---")
    st.markdown("### 💾 Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Export to CSV"):
            if not perf_data.empty:
                csv = perf_data.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    "performance_data.csv",
                    "text/csv",
                    key='download-csv'
                )
    
    with col2:
        if st.button("📈 Generate Report"):
            st.info("Report generation coming soon")
    
    with col3:
        if st.button("🖨️ Print Summary"):
            st.info("Print feature coming soon")


def create_performance_chart(data: pd.DataFrame, chart_type: str) -> go.Figure:
    """Create main performance chart"""
    
    fig = go.Figure()
    
    if chart_type == "Line":
        fig.add_trace(go.Scatter(
            x=data['date'],
            y=data['cumulative_pnl'],
            mode='lines',
            name='Cumulative P&L',
            line=dict(color='#00cc00', width=2)
        ))
    elif chart_type == "Area":
        fig.add_trace(go.Scatter(
            x=data['date'],
            y=data['cumulative_pnl'],
            mode='lines',
            fill='tozeroy',
            name='Cumulative P&L',
            line=dict(color='#00cc00', width=2)
        ))
    else:  # Bar
        colors = ['green' if x >= 0 else 'red' for x in data['daily_pnl']]
        fig.add_trace(go.Bar(
            x=data['date'],
            y=data['daily_pnl'],
            name='Daily P&L',
            marker_color=colors
        ))
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    
    fig.update_layout(
        title="Performance Over Time",
        xaxis_title="Date",
        yaxis_title="P&L ($)",
        hovermode='x unified',
        showlegend=False,
        height=500
    )
    
    return fig


def calculate_returns_metrics(data: pd.DataFrame) -> dict:
    """Calculate returns-based metrics"""
    
    daily_returns = data['daily_pnl'].values
    
    return {
        'total_return': data['cumulative_pnl'].iloc[-1],
        'avg_daily': daily_returns.mean(),
        'best_day': daily_returns.max(),
        'worst_day': daily_returns.min(),
        'positive_days': (daily_returns > 0).sum(),
        'negative_days': (daily_returns < 0).sum(),
        'max_consecutive_wins': calculate_max_consecutive(daily_returns > 0),
        'max_consecutive_losses': calculate_max_consecutive(daily_returns < 0)
    }


def calculate_risk_metrics(data: pd.DataFrame) -> dict:
    """Calculate risk-based metrics"""
    
    daily_returns = data['daily_pnl'].values / 10000  # Normalize by initial capital
    
    # Sharpe Ratio (assuming 0% risk-free rate)
    sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() > 0 else 0
    
    # Sortino Ratio
    downside_returns = daily_returns[daily_returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
    sortino = np.sqrt(252) * daily_returns.mean() / downside_std if downside_std > 0 else 0
    
    # Drawdown
    cumulative = data['cumulative_pnl'].values
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    
    # Profit Factor
    gains = daily_returns[daily_returns > 0].sum()
    losses = abs(daily_returns[daily_returns < 0].sum())
    profit_factor = gains / losses if losses > 0 else 0
    
    return {
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'max_drawdown': drawdown.min() if len(drawdown) > 0 else 0,
        'avg_drawdown': drawdown.mean() if len(drawdown) > 0 else 0,
        'volatility': daily_returns.std(),
        'downside_deviation': downside_std,
        'profit_factor': profit_factor,
        'recovery_factor': abs(cumulative[-1] / drawdown.min()) if drawdown.min() < 0 else 0
    }


def calculate_max_consecutive(series: pd.Series) -> int:
    """Calculate maximum consecutive True values"""
    
    max_consecutive = 0
    current = 0
    
    for value in series:
        if value:
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 0
    
    return max_consecutive


def create_monthly_heatmap_data(data: pd.DataFrame) -> dict:
    """Create data for monthly heatmap"""
    
    # Add month and day columns
    data['month'] = pd.to_datetime(data['date']).dt.strftime('%Y-%m')
    data['day'] = pd.to_datetime(data['date']).dt.day
    
    # Pivot data
    pivot = data.pivot_table(
        values='daily_pnl',
        index='month',
        columns='day',
        aggfunc='sum'
    )
    
    # Format text for heatmap
    text = pivot.applymap(lambda x: f"${x:.0f}" if pd.notna(x) else "")
    
    return {
        'returns': pivot.values,
        'days': list(range(1, 32)),
        'months': pivot.index.tolist(),
        'text': text.values
    }


def generate_sample_performance_data(days: int) -> pd.DataFrame:
    """Generate sample performance data for demonstration"""
    
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate realistic trading data
    daily_pnl = np.random.normal(50, 200, days)  # Average $50 profit with $200 std dev
    daily_pnl[np.random.choice(days, int(days * 0.1))] *= -2  # Some bad days
    
    trades = np.random.poisson(10, days)  # Average 10 trades per day
    wins = np.minimum(trades, np.random.binomial(trades, 0.55))  # 55% win rate
    
    df = pd.DataFrame({
        'date': dates,
        'daily_pnl': daily_pnl,
        'trades': trades,
        'wins': wins
    })
    
    df['cumulative_pnl'] = df['daily_pnl'].cumsum()
    df['win_rate'] = (df['wins'] / df['trades'] * 100).fillna(0)
    
    return df