import pandas as pd
import numpy as np
import os
from liquidity_sweep import LiquiditySweepDetector, load_data
from macro_engine import MacroEngine
import joblib

def check_missed_setups(symbol, file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"\n--- Checking {symbol} for missed setups (Last 4 hours) ---")
    df = load_data(file_path)
    
    # Initialize Macro Engine and load models
    macro = MacroEngine()
    d1_model_path = "smc_ai_trading_system/models/d1_lightgbm.pkl"
    h1_model_path = "smc_ai_trading_system/models/h1_lightgbm.pkl"
    
    if os.path.exists(d1_model_path) and os.path.exists(h1_model_path):
        macro.d1_model = joblib.load(d1_model_path)
        macro.h1_model = joblib.load(h1_model_path)
        
        # Populate caches for the last few days/hours
        # D1 Cache
        d1_df_path = f"smc_ai_trading_system/data/{symbol}_D1.csv"
        if os.path.exists(d1_df_path):
            d1_df = pd.read_csv(d1_df_path, sep='\t')
            d1_df.rename(columns={'<DATE>': 'date', '<CLOSE>': 'close', '<HIGH>': 'high', '<LOW>': 'low'}, inplace=True)
            f_d1 = macro.prepare_features(d1_df)
            probs = macro.d1_model.predict_proba(f_d1[['returns', 'range', 'volatility', 'dist_sma', 'rsi']])[:, 1]
            macro.daily_bias_cache = dict(zip(f_d1['date'], probs))
        
        # H1 Cache
        h1_df_path = f"smc_ai_trading_system/data/{symbol}_H1.csv"
        if os.path.exists(h1_df_path):
            h1_df = pd.read_csv(h1_df_path, sep='\t')
            h1_df.rename(columns={'<DATE>': 'date', '<TIME>': 'time', '<CLOSE>': 'close', '<HIGH>': 'high', '<LOW>': 'low'}, inplace=True)
            h1_df['datetime'] = pd.to_datetime(h1_df['date'] + ' ' + h1_df['time'])
            f_h1 = macro.prepare_features(h1_df)
            probs = macro.h1_model.predict_proba(f_h1[['returns', 'range', 'volatility', 'dist_sma', 'rsi']])[:, 1]
            macro.hourly_bias_cache = dict(zip(f_h1['datetime'], probs))

    # Resetting the detector each time to clear swing lists
    detector = LiquiditySweepDetector(fractal_window=2, macro_engine=macro)
    df_with_fractals = detector.identify_fractals(df)
    
    # We run detect_sweeps with a lower threshold (0.5) to see ALL raw signals
    all_raw_signals = detector.detect_sweeps(df_with_fractals, d1_threshold=0.5, h1_threshold=0.5)
    
    if all_raw_signals.empty:
        print(f"No raw liquidity sweeps detected in history for {symbol}.")
        return

    # Filter for the last 4 hours
    last_time = df.index[-1]
    four_hours_ago = last_time - pd.Timedelta(hours=4)
    recent_signals = all_raw_signals[all_raw_signals['time'] >= four_hours_ago]

    if recent_signals.empty:
        print(f"No liquidity sweeps detected in the last 4 hours for {symbol}.")
        print(f"Latest candle time in data: {last_time}")
    else:
        print(f"Found {len(recent_signals)} recent raw signals:")
        # Select columns that exist
        cols = ['time', 'type', 'level_price', 'entry', 'd1_bias', 'h1_bias']
        present_cols = [c for c in cols if c in recent_signals.columns]
        print(recent_signals[present_cols])
        
        # Check if any would have passed the 0.6 threshold
        passed = recent_signals[(recent_signals['d1_bias'] >= 0.6) & (recent_signals['h1_bias'] >= 0.6)]
        if not passed.empty:
            print("\n!!! THESE SIGNALS SHOULD HAVE TRIGGERED (PASSED 0.6) !!!")
            print(passed[present_cols])
        else:
            print("\nNone of these signals passed the 0.6 AI threshold.")

if __name__ == "__main__":
    check_missed_setups("BTCUSD.p", "smc_ai_trading_system/data/BTCUSD.p_M15.csv")
    check_missed_setups("NDXUSD.p", "smc_ai_trading_system/data/NDXUSD.p_M15.csv")
