"""
Deploy Strategy Page
Configure and deploy trading strategies
"""

import streamlit as st
import yaml
from typing import Dict, Any
import json

from services.data_service import DataService


def render():
    """Render the deploy strategy page"""
    
    # Initialize data service
    data_service = DataService()
    
    st.subheader("🚀 Deploy Trading Strategy")
    st.markdown("Configure and deploy your trading strategy with custom parameters")
    
    # Load current configuration
    current_config = data_service.load_config()
    
    # Strategy selection
    st.markdown("### 1️⃣ Select Strategy Type")
    
    col1, col2 = st.columns([2, 3])
    
    with col1:
        strategy_types = {
            "grid": "Grid Trading",
            "momentum": "Momentum Trading",
            "ema_cross": "EMA Cross",
            "mean_reversion": "Mean Reversion"
        }
        
        selected_strategy = st.selectbox(
            "Strategy Type",
            options=list(strategy_types.keys()),
            format_func=lambda x: strategy_types[x],
            help="Select the trading strategy to deploy"
        )
        
        # Strategy description
        strategy_descriptions = {
            "grid": "Places buy and sell orders at fixed intervals to profit from volatility",
            "momentum": "Follows market trends using technical indicators",
            "ema_cross": "Trades based on EMA crossover signals",
            "mean_reversion": "Trades expecting price to revert to mean"
        }
        
        st.info(strategy_descriptions.get(selected_strategy, ""))
    
    with col2:
        # Show current active strategy
        st.markdown("**Currently Active Strategy:**")
        active_strategy = None
        for strategy, config in current_config.get('strategy', {}).items():
            if isinstance(config, dict) and config.get('enabled'):
                active_strategy = strategy
                break
        
        if active_strategy:
            st.success(f"✅ {strategy_types.get(active_strategy, active_strategy)} is running")
        else:
            st.warning("⚠️ No strategy currently active")
    
    st.markdown("---")
    
    # Symbol and timeframe configuration
    st.markdown("### 2️⃣ Symbol Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "LINKUSDT", "ADAUSDT", "DOGEUSDT"]
        selected_symbol = st.selectbox(
            "Trading Pair",
            options=symbols,
            help="Select the cryptocurrency pair to trade"
        )
    
    with col2:
        timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        selected_timeframe = st.selectbox(
            "Timeframe",
            options=timeframes,
            index=4,  # Default to 1h
            help="Select the candlestick timeframe"
        )
    
    with col3:
        capital = st.number_input(
            "Initial Capital ($)",
            min_value=100,
            max_value=1000000,
            value=current_config.get('capital', {}).get('initial_capital', 500),
            step=100,
            help="Amount of capital to allocate"
        )
    
    st.markdown("---")
    
    # Strategy-specific parameters
    st.markdown("### 3️⃣ Strategy Parameters")
    
    strategy_params = {}
    
    if selected_strategy == "grid":
        col1, col2 = st.columns(2)
        
        with col1:
            strategy_params['grid_levels'] = st.number_input(
                "Grid Levels",
                min_value=5,
                max_value=50,
                value=10,
                help="Number of grid levels to create"
            )
            
            strategy_params['grid_spacing'] = st.slider(
                "Grid Spacing (%)",
                min_value=0.1,
                max_value=5.0,
                value=0.5,
                step=0.1,
                help="Percentage spacing between grid levels"
            ) / 100
            
            strategy_params['use_dynamic_grid'] = st.checkbox(
                "Dynamic Grid Adjustment",
                value=True,
                help="Automatically adjust grid based on volatility"
            )
        
        with col2:
            strategy_params['position_size_per_grid'] = st.slider(
                "Position Size per Grid (%)",
                min_value=1,
                max_value=20,
                value=5,
                help="Percentage of capital per grid level"
            ) / 100
            
            if strategy_params['use_dynamic_grid']:
                strategy_params['atr_period'] = st.number_input(
                    "ATR Period",
                    min_value=5,
                    max_value=50,
                    value=14,
                    help="Period for ATR calculation"
                )
                
                strategy_params['atr_multiplier'] = st.slider(
                    "ATR Multiplier",
                    min_value=0.5,
                    max_value=3.0,
                    value=1.5,
                    step=0.1,
                    help="Multiplier for dynamic grid spacing"
                )
    
    elif selected_strategy == "momentum":
        col1, col2 = st.columns(2)
        
        with col1:
            strategy_params['fast_period'] = st.number_input(
                "Fast MA Period",
                min_value=5,
                max_value=50,
                value=8,
                help="Fast moving average period"
            )
            
            strategy_params['slow_period'] = st.number_input(
                "Slow MA Period",
                min_value=10,
                max_value=200,
                value=21,
                help="Slow moving average period"
            )
            
            strategy_params['position_size'] = st.slider(
                "Position Size (%)",
                min_value=10,
                max_value=100,
                value=95,
                help="Percentage of capital to use"
            ) / 100
        
        with col2:
            strategy_params['stop_loss_pct'] = st.slider(
                "Stop Loss (%)",
                min_value=0.5,
                max_value=10.0,
                value=3.0,
                step=0.5,
                help="Stop loss percentage"
            ) / 100
            
            strategy_params['take_profit_pct'] = st.slider(
                "Take Profit (%)",
                min_value=1.0,
                max_value=20.0,
                value=10.0,
                step=0.5,
                help="Take profit percentage"
            ) / 100
    
    elif selected_strategy == "ema_cross":
        col1, col2 = st.columns(2)
        
        with col1:
            strategy_params['fast_period'] = st.number_input(
                "Fast EMA Period",
                min_value=5,
                max_value=50,
                value=9,
                help="Fast EMA period"
            )
            
            strategy_params['slow_period'] = st.number_input(
                "Slow EMA Period",
                min_value=10,
                max_value=200,
                value=21,
                help="Slow EMA period"
            )
        
        with col2:
            strategy_params['stop_loss'] = st.slider(
                "Stop Loss (%)",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.5,
                help="Stop loss percentage"
            ) / 100
            
            strategy_params['take_profit'] = st.slider(
                "Take Profit (%)",
                min_value=1.0,
                max_value=10.0,
                value=5.0,
                step=0.5,
                help="Take profit percentage"
            ) / 100
    
    else:  # mean_reversion
        st.info("Mean Reversion strategy parameters coming soon")
    
    st.markdown("---")
    
    # Risk Management Settings
    st.markdown("### 4️⃣ Risk Management")
    
    col1, col2, col3 = st.columns(3)
    
    risk_limits = {}
    
    with col1:
        risk_limits['max_position_size_pct'] = st.slider(
            "Max Position Size (%)",
            min_value=5,
            max_value=50,
            value=10,
            help="Maximum size for a single position"
        ) / 100
        
        risk_limits['max_positions'] = st.number_input(
            "Max Positions",
            min_value=1,
            max_value=20,
            value=10,
            help="Maximum number of concurrent positions"
        )
    
    with col2:
        risk_limits['max_daily_loss_pct'] = st.slider(
            "Max Daily Loss (%)",
            min_value=1,
            max_value=10,
            value=2,
            help="Stop trading if daily loss exceeds this"
        ) / 100
        
        risk_limits['max_drawdown_pct'] = st.slider(
            "Max Drawdown (%)",
            min_value=5,
            max_value=30,
            value=10,
            help="Stop trading if drawdown exceeds this"
        ) / 100
    
    with col3:
        risk_limits['max_leverage'] = st.slider(
            "Max Leverage",
            min_value=1,
            max_value=10,
            value=2,
            help="Maximum leverage to use"
        )
        
        risk_limits['emergency_stop_loss_pct'] = st.slider(
            "Emergency Stop (%)",
            min_value=10,
            max_value=50,
            value=15,
            help="Emergency stop loss percentage"
        ) / 100
    
    st.markdown("---")
    
    # Configuration Summary
    st.markdown("### 📋 Configuration Summary")
    
    config_summary = {
        "Strategy": strategy_types[selected_strategy],
        "Symbol": selected_symbol,
        "Timeframe": selected_timeframe,
        "Capital": f"${capital:,}",
        "Parameters": strategy_params,
        "Risk Limits": {
            "Max Position Size": f"{risk_limits['max_position_size_pct']*100:.0f}%",
            "Max Daily Loss": f"{risk_limits['max_daily_loss_pct']*100:.0f}%",
            "Max Drawdown": f"{risk_limits['max_drawdown_pct']*100:.0f}%"
        }
    }
    
    # Display summary in expandable section
    with st.expander("View Full Configuration", expanded=True):
        st.json(config_summary)
    
    st.markdown("---")
    
    # Deployment Actions
    st.markdown("### 5️⃣ Deploy Strategy")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        deployment_mode = st.radio(
            "Deployment Mode",
            options=["testnet", "production"],
            format_func=lambda x: "Testnet (Safe)" if x == "testnet" else "Production (Real Money)",
            help="Choose deployment environment"
        )
    
    with col2:
        dry_run = st.checkbox(
            "Dry Run Mode",
            value=True,
            help="Simulate trades without real orders"
        )
    
    with col3:
        st.markdown("") # Spacer
        st.markdown("") # Spacer
        
    # Deploy button with confirmation
    if st.button("🚀 Deploy Strategy", type="primary", use_container_width=True):
        if deployment_mode == "production" and not dry_run:
            st.warning("⚠️ You are about to deploy with REAL MONEY!")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.checkbox("I understand the risks"):
                    confirm_text = st.text_input("Type 'DEPLOY' to confirm")
                    if confirm_text == "DEPLOY":
                        deploy_strategy(data_service, selected_strategy, selected_symbol, 
                                      selected_timeframe, strategy_params, risk_limits, 
                                      capital, deployment_mode, dry_run)
            with col2:
                st.error("Real money trading - be careful!")
        else:
            deploy_strategy(data_service, selected_strategy, selected_symbol, 
                          selected_timeframe, strategy_params, risk_limits, 
                          capital, deployment_mode, dry_run)
    
    # Quick Actions
    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Load Current Config"):
            st.info("Loading current configuration...")
            st.rerun()
    
    with col2:
        if st.button("Save as Template"):
            st.success("Configuration saved as template")
    
    with col3:
        if st.button("Load Template"):
            st.info("Template loading coming soon")
    
    with col4:
        if st.button("Reset to Defaults"):
            st.warning("Reset to default values")
            st.rerun()


def deploy_strategy(data_service, strategy_type, symbol, timeframe, 
                    strategy_params, risk_limits, capital, mode, dry_run):
    """Deploy the configured strategy"""
    
    # Prepare deployment configuration
    deployment_config = {
        'type': strategy_type,
        'params': {
            'symbol': symbol,
            'interval': timeframe,
            **strategy_params
        },
        'capital': capital,
        'risk_limits': risk_limits,
        'mode': mode,
        'dry_run': dry_run
    }
    
    # Show deployment progress
    with st.spinner("Deploying strategy..."):
        try:
            # Deploy through data service
            success = data_service.deploy_strategy(deployment_config)
            
            if success:
                st.success(f"""
                ✅ Strategy Deployed Successfully!
                
                - Strategy: {strategy_type.upper()}
                - Symbol: {symbol}
                - Timeframe: {timeframe}
                - Mode: {'Testnet' if mode == 'testnet' else 'Production'}
                - Dry Run: {'Yes' if dry_run else 'No'}
                
                The strategy is now running. Check the Live Monitoring page for real-time updates.
                """)
                
                # Show next steps
                st.info("""
                **Next Steps:**
                1. Go to Live Monitoring to watch your positions
                2. Check Risk Management for safety controls
                3. Monitor the logs for detailed information
                """)
            else:
                st.error("Failed to deploy strategy. Please check the logs.")
                
        except Exception as e:
            st.error(f"Deployment error: {str(e)}")
            st.exception(e)