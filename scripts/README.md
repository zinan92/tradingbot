# Scripts Directory

This directory contains all executable Python scripts organized by functionality.

## Directory Structure

```
scripts/
├── analysis/         # Data and results analysis scripts
├── backtesting/      # Strategy backtesting scripts
├── data_download/    # Market data download scripts
├── indicators/       # Technical indicator calculation scripts
└── utils/           # Utility and helper scripts
```

## Usage

All scripts automatically add the project root to the Python path, so they can be run from any location:

```bash
# Run from project root
python scripts/backtesting/run_optimal_grid_backtest.py

# Or make executable and run directly
chmod +x scripts/analysis/analyze_optimal_grid.py
./scripts/analysis/analyze_optimal_grid.py
```

## Subdirectories

- **analysis/**: Scripts for analyzing backtest results, trade performance, and strategy metrics
- **backtesting/**: Scripts to run various backtesting strategies and compare results
- **data_download/**: Scripts for downloading historical market data from exchanges
- **indicators/**: Scripts for calculating and storing technical indicators
- **utils/**: Helper scripts for data validation, testing connections, and debugging

## Note

All output files (CSVs, HTMLs, logs) are saved to the `outputs/` directory, not in the script directories.