#!/usr/bin/env python3
"""
Custom symbol list for historical data download
"""

# Original top 30 by volume
original_symbols = [
    "ETHUSDT",      # 1
    "BTCUSDT",      # 2
    "SOLUSDT",      # 3
    "ALPACAUSDT",   # 4 - REMOVE
    "MYXUSDT",      # 5 - REMOVE
    "XRPUSDT",      # 6
    "DOGEUSDT",     # 7
    "ENAUSDT",      # 8
    "MEMEFIUSDT",   # 9 - REMOVE
    "SUIUSDT",      # 10
    "PROVEUSDT",    # 11 - REMOVE
    "1000PEPEUSDT", # 12
    "LTCUSDT",      # 13
    "BNXUSDT",      # 14 - REMOVE
    "PENGUUSDT",    # 15 - REMOVE
    "ADAUSDT",      # 16
    "BNBUSDT",      # 17
    "VELVETUSDT",   # 18 - REMOVE
    "FARTCOINUSDT", # 19
    "PUMPUSDT",     # 20 - REMOVE
    "PLAYUSDT",     # 21 - REMOVE
    "OMNIUSDT",     # 22 - REMOVE
    "DMCUSDT",      # 23 - REMOVE
    "LINKUSDT",     # 24
    "TOWNSUSDT",    # 25 - REMOVE
    "BCHUSDT",      # 26
    "AVAXUSDT",     # 27
    "WIFUSDT",      # 28
    "TSTUSDT",      # 29 - REMOVE
    "CFXUSDT",      # 30 - REMOVE
]

# Symbols to remove (indices from user)
remove_indices = [4, 5, 9, 11, 14, 15, 18, 20, 21, 22, 23, 25, 29, 30]

# Keep these symbols
keep_symbols = [
    "ETHUSDT",       # 1
    "BTCUSDT",       # 2
    "SOLUSDT",       # 3
    "XRPUSDT",       # 6
    "DOGEUSDT",      # 7
    "ENAUSDT",       # 8
    "SUIUSDT",       # 10
    "1000PEPEUSDT",  # 12
    "LTCUSDT",       # 13
    "ADAUSDT",       # 16
    "BNBUSDT",       # 17 - Already in your database with 52,560 candles
    "FARTCOINUSDT",  # 19
    "LINKUSDT",      # 24
    "BCHUSDT",       # 26
    "AVAXUSDT",      # 27
    "WIFUSDT",       # 28
]

# New symbols to add
new_symbols = [
    "AAVEUSDT",
    "JUPUSDT",
    "1000BONKUSDT",
    "JTOUSDT",
    "UNIUSDT",
    "SUSHIUSDT",
    "CRVUSDT",
    "LDOUSDT",
    "PENDLEUSDT",
    "ONDOUSDT",
    "1000SHIBUSDT",
]

# Combine and check for duplicates
final_symbols = keep_symbols + new_symbols

# Check for duplicates
duplicates = []
seen = set()
for symbol in final_symbols:
    if symbol in seen:
        duplicates.append(symbol)
    seen.add(symbol)

# Final unique list
CUSTOM_SYMBOLS = list(dict.fromkeys(final_symbols))  # Preserves order, removes duplicates

if __name__ == "__main__":
    print(f"Total symbols: {len(CUSTOM_SYMBOLS)}")
    print(f"Duplicates found: {duplicates if duplicates else 'None'}")
    print("\nFinal symbol list:")
    for i, symbol in enumerate(CUSTOM_SYMBOLS, 1):
        status = ""
        if symbol in ["ETHUSDT", "BTCUSDT", "SOLUSDT"]:
            status = " ✅ (already complete)"
        elif symbol == "BNBUSDT":
            status = " ⚠️ (partial data)"
        elif symbol in new_symbols:
            status = " 🆕 (new)"
        print(f"{i:2d}. {symbol}{status}")