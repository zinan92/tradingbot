"""
Setup configuration for the trading bot with hexagonal architecture plugin.
"""

from setuptools import setup, find_packages

setup(
    name="tradingbot-v2",
    version="2.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    
    # Flake8 plugin entry point
    entry_points={
        "flake8.extension": [
            "HEX = flake8_hexagonal:HexagonalArchitectureChecker",
        ],
    },
    
    # Plugin module
    py_modules=["flake8_hexagonal"],
    
    install_requires=[
        "pydantic>=2.0.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "flake8>=6.0.0",
        "black>=23.0.0",
        "mypy>=1.0.0",
    ],
    
    extras_require={
        "dev": [
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "hypothesis>=6.0.0",
        ],
        "cli": [
            "click>=8.1.0",
            "rich>=13.0.0",
            "aiohttp>=3.9.0",
        ],
    },
    
    author="Trading Bot Team",
    description="Trading bot with hexagonal architecture",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
)