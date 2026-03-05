import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

from macro_engine import MacroEngine

class LiquiditySweepDetector:
    def __init__(self, fractal_window=2, macro_engine=None):
        self.fractal_window = fractal_window
        self.macro_engine = macro_engine
        self.swing_highs = [] 
        self.swing_lows = []

    def identify_fractals(self, df):
        """
        Identifies Swing Highs and Swing Lows using fractal logic.
        Adds ATR for dynamic SL/TP.
        """
        df = df.copy()
        df['swing_high'] = np.nan
        df['swing_low'] = np.nan
        
        # Clear previous state to prevent memory leak/redundancy
        self.swing_highs = []
        self.swing_lows = []
        
        # Calculate ATR (14 period)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()

        for i in range(self.fractal_window, len(df) - self.fractal_window):
            # Swing Low (Fractal Low)
            window_lows = df['low'].iloc[i - self.fractal_window : i + self.fractal_window + 1]
            if df['low'].iloc[i] == window_lows.min():
                df.at[df.index[i], 'swing_low'] = df['low'].iloc[i]
                self.swing_lows.append({'index': df.index[i], 'price': df['low'].iloc[i], 'active': True})

            # Swing High (Fractal High)
            window_highs = df['high'].iloc[i - self.fractal_window : i + self.fractal_window + 1]
            if df['high'].iloc[i] == window_highs.max():
                df.at[df.index[i], 'swing_high'] = df['high'].iloc[i]
                self.swing_highs.append({'index': df.index[i], 'price': df['high'].iloc[i], 'active': True})

        return df

    def detect_sweeps(self, df, htf_threshold=0.6, ltf_threshold=0.6, rr_ratio=2.0):
        signals = []
        # We only look at completed candles
        for i in range(self.fractal_window + 1, len(df) - 1):
            current_candle = df.iloc[i]
            current_idx = df.index[i]
            atr = current_candle['atr'] if not np.isnan(current_candle['atr']) else 0.0001
            
            # Query Macro Bias
            htf_bias, ltf_bias = (0.5, 0.5)
            if self.macro_engine:
                htf_bias, ltf_bias = self.macro_engine.get_bias(current_idx)

            # --- BUY SWEEP (Bullish Bias) ---
            for sl in self.swing_lows:
                if not sl['active'] or current_idx <= sl['index']:
                    continue
                
                # Check for Sweep + Displacement Confirmation
                if htf_bias > htf_threshold and ltf_bias > ltf_threshold:
                    prev_candle = df.iloc[i-1]
                    # Sweep: Low < Level and Close > Level
                    # Confirmation: Green candle closing above previous Close
                    if current_candle['low'] < sl['price'] and current_candle['close'] > sl['price']:
                        if current_candle['close'] > prev_candle['close'] and current_candle['close'] > current_candle['open']:
                            entry = current_candle['close']
                            stop_loss = current_candle['low'] - (atr * 0.1)
                            risk = entry - stop_loss
                            take_profit = entry + (risk * rr_ratio)
                            
                            signals.append({
                                'time': current_idx, 'type': 'BULLISH_SWEEP',
                                'htf_bias': htf_bias, 'ltf_bias': ltf_bias,
                                'level_price': sl['price'], 'entry': entry,
                                'stop_loss': stop_loss, 'take_profit': take_profit,
                                'valid': True
                            })
                            sl['active'] = False
                            break

            # --- SELL SWEEP (Bearish Bias) ---
            for sh in self.swing_highs:
                if not sh['active'] or current_idx <= sh['index']:
                    continue
                
                # Check for Sweep + Displacement Confirmation
                if htf_bias < (1 - htf_threshold) and ltf_bias < (1 - ltf_threshold):
                    prev_candle = df.iloc[i-1]
                    # Sweep: High > Level and Close < Level
                    # Confirmation: Red candle closing below previous Close
                    if current_candle['high'] > sh['price'] and current_candle['close'] < sh['price']:
                        if current_candle['close'] < prev_candle['close'] and current_candle['close'] < current_candle['open']:
                            entry = current_candle['close']
                            stop_loss = current_candle['high'] + (atr * 0.1)
                            risk = stop_loss - entry
                            take_profit = entry - (risk * rr_ratio)
                            
                            signals.append({
                                'time': current_idx, 'type': 'BEARISH_SWEEP',
                                'htf_bias': htf_bias, 'ltf_bias': ltf_bias,
                                'level_price': sh['price'], 'entry': entry,
                                'stop_loss': stop_loss, 'take_profit': take_profit,
                                'valid': True
                            })
                            sh['active'] = False
                            break
        return pd.DataFrame(signals)

    def plot_sweep(self, df, sweep_signal, window=20):
        """
        Plots a small window of data around a detected sweep.
        """
        sweep_time = sweep_signal['time']
        start_idx = df.index.get_loc(sweep_time) - window
        end_idx = df.index.get_loc(sweep_time) + 5
        
        plot_df = df.iloc[start_idx:end_idx]
        
        plt.figure(figsize=(12, 6))
        # Simple line plot for visual check (not a candlestick but serves verification)
        plt.plot(plot_df.index, plot_df['close'], label='Close Price', color='black', alpha=0.3)
        plt.vlines(plot_df.index, plot_df['low'], plot_df['high'], color='gray')
        
        # Mark the sweep candle
        plt.scatter(sweep_time, sweep_signal['entry'], color='green' if 'BULLISH' in sweep_signal['type'] else 'red', 
                    label=f"Signal: {sweep_signal['type']}", zorder=5)
        
        # Mark the level that was swept
        plt.axhline(y=sweep_signal['level_price'], color='blue', linestyle='--', label=f"Swept Level: {sweep_signal['level_price']:.5f}")
        
        plt.title(f"Liquidity Sweep Detection: {sweep_signal['type']} at {sweep_time}")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Save plot for user to see
        filename = f"sweep_{sweep_time.strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(f"smc_ai_trading_system/{filename}")
        print(f"Saved verification plot: smc_ai_trading_system/{filename}")
        plt.close()

def load_data(file_path):
    df = pd.read_csv(file_path, sep='\t')
    mapping = {'<DATE>': 'date', '<TIME>': 'time', '<OPEN>': 'open', '<HIGH>': 'high', '<LOW>': 'low', '<CLOSE>': 'close'}
    df.rename(columns=mapping, inplace=True)
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    df.set_index('datetime', inplace=True)
    return df

if __name__ == "__main__":
    sample_path = "/home/add/Desktop/Git/qlib_mql5_bot/history_data/EURUSD.p_M15_202501020000_202602271530.csv"
    
    if os.path.exists(sample_path):
        print(f"Loading data from {sample_path}...")
        df = load_data(sample_path)
        
        detector = LiquiditySweepDetector(fractal_window=2)
        print("Identifying Fractals...")
        df_with_fractals = detector.identify_fractals(df)
        
        print("Detecting Sweeps...")
        sweep_signals = detector.detect_sweeps(df_with_fractals)
        
        if not sweep_signals.empty:
            print("\n--- LAST 5 LIQUIDITY SWEEP SIGNALS ---")
            print(sweep_signals.tail(5))
            
            # Plot the very last sweep found
            last_sweep = sweep_signals.iloc[-1]
            detector.plot_sweep(df, last_sweep)
        else:
            print("No sweeps detected.")
    else:
        print("Sample file not found.")
