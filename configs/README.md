# Configs Directory

This directory contains configuration files for various scripts and components.

## Configuration Files

- `download_config.json` - Configuration for historical data downloads
- `test_download_config.json` - Test configuration for download scripts
- `download_report_*.json` - Generated reports from download sessions

## Usage

Configuration files are referenced by scripts in the `scripts/` directory. When running scripts, they will automatically look for configs in this directory.

## Main Configuration

The primary application configuration (`config.yaml`) remains in the project root for easy access and Docker compatibility.

## Security Note

Never commit sensitive information (API keys, passwords, etc.) to configuration files. Use environment variables or secure secret management systems for sensitive data.