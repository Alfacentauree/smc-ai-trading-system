import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from liquidity_sweep import LiquiditySweepDetector, load_data

# Load M15 data
df = load_data("smc_ai_trading_system/data/NDXUSD.p_M15.csv")
df = df.tail(100) # Last 100 candles for clarity

detector = LiquiditySweepDetector(fractal_window=2)
df = detector.identify_fractals(df)

plt.figure(figsize=(15, 8))
plt.plot(df.index, df['close'], color='black', alpha=0.4, label='Price (Close)')
plt.vlines(df.index, df['low'], df['high'], color='gray', alpha=0.3)

# Plot Swing Highs
sh = df[df['swing_high'].notnull()]
plt.scatter(sh.index, sh['swing_high'], color='red', marker='v', s=100, label='Swing High (Resistance/Liquidity)')

# Plot Swing Lows
sl = df[df['swing_low'].notnull()]
plt.scatter(sl.index, sl['swing_low'], color='blue', marker='^', s=100, label='Swing Low (Support/Liquidity)')

plt.title("SMC Concept: Swing Highs & Swing Lows (Fractals)")
plt.legend()
plt.grid(True, alpha=0.2)
plt.savefig("swing_explanation.png")
print("Graph saved as swing_explanation.png")
