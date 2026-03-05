import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from macro_engine import MacroEngine
from liquidity_sweep import LiquiditySweepDetector, load_data

class SMCBacktester:
    def __init__(self, symbol, initial_balance=5000):
        self.symbol = symbol
        self.balance = initial_balance
        self.equity_curve = [initial_balance]
        self.macro = MacroEngine()
        self.detector = LiquiditySweepDetector(fractal_window=2, macro_engine=self.macro)

    def run_backtest(self, d1_file, h1_file, m15_file):
        print(f"\n--- Backtesting SMC AI System for {self.symbol} ---")
        
        try:
            # 1. Train Macro
            self.macro.train_d1_model(d1_file)
            self.macro.train_h1_model(h1_file)
            
            # 2. Detect Signals on 15m Data
            df = load_data(m15_file)
            df = self.detector.identify_fractals(df)
            signals = self.detector.detect_sweeps(df, rr_ratio=2.0)
            
            if signals.empty:
                print("No signals found in the backtest period.")
                return

            print(f"Found {len(signals)} signals. Simulating trades (RR 1:2)...")
            
            results = []
            for i, sig in signals.iterrows():
                # Trade Parameters from Signal
                entry_price = sig['entry']
                initial_sl = sig['stop_loss']
                initial_risk = abs(entry_price - initial_sl)
                trailing_sl = initial_sl
                peak_price = entry_price
                be_triggered = False # Break-even / Trail trigger
                
                # Find the outcome (look ahead in data)
                try:
                    start_idx = df.index.get_loc(sig['time'])
                except KeyError:
                    continue
                    
                future_data = df.iloc[start_idx+1 : start_idx+300] # Check more candles for trailing
                
                exit_price = None
                
                for _, candle in future_data.iterrows():
                    if "BULLISH" in sig['type']:
                        # Update Peak
                        if candle['high'] > peak_price:
                            peak_price = candle['high']
                            
                        # Check for 1:1 RR trigger
                        if not be_triggered and (peak_price - entry_price) >= initial_risk:
                            be_triggered = True
                            trailing_sl = entry_price # Move to Break-even
                        
                        # If triggered, update trailing SL
                        if be_triggered:
                            new_sl = peak_price - initial_risk
                            if new_sl > trailing_sl:
                                trailing_sl = new_sl
                        
                        # Check if SL hit
                        if candle['low'] <= trailing_sl:
                            exit_price = trailing_sl
                            break
                            
                    else: # BEARISH
                        # Update Peak (Lowest)
                        if candle['low'] < peak_price:
                            peak_price = candle['low']
                            
                        # Check for 1:1 RR trigger
                        if not be_triggered and (entry_price - peak_price) >= initial_risk:
                            be_triggered = True
                            trailing_sl = entry_price # Move to Break-even
                            
                        # If triggered, update trailing SL
                        if be_triggered:
                            new_sl = peak_price + initial_risk
                            if new_sl < trailing_sl:
                                trailing_sl = new_sl
                        
                        # Check if SL hit
                        if candle['high'] >= trailing_sl:
                            exit_price = trailing_sl
                            break
                
                if exit_price is not None:
                    # Calculate actual profit/loss
                    risk_amount_dollars = self.balance * 0.01
                    price_diff = exit_price - entry_price if "BULLISH" in sig['type'] else entry_price - exit_price
                    
                    # Profit/Loss in terms of R-multiples
                    r_multiple = price_diff / initial_risk
                    profit = r_multiple * risk_amount_dollars
                    
                    outcome = "WIN" if profit > 0 else "LOSS"
                    
                    self.balance += profit
                    self.equity_curve.append(self.balance)
                    results.append({'time': sig['time'], 'type': sig['type'], 'outcome': outcome, 'profit': profit})

            if not results:
                print("No trades were closed during the simulation.")
                return

            # 3. Report Results
            res_df = pd.DataFrame(results)
            win_rate = (len(res_df[res_df['outcome']=='WIN']) / len(res_df)) * 100
            
            print(f"\n--- BACKTEST REPORT (SMART TRAILING SL) ---")
            print(f"Total Trades:      {len(res_df)}")
            print(f"Win Rate:          {win_rate:.2f}%")
            print(f"Final Balance:     ${self.balance:,.2f}")
            print(f"Net Profit:        ${self.balance - 5000:,.2f} ({(self.balance - 5000)/50:.2f}%)")
            
            # 4. Plot Equity Curve
            plt.figure(figsize=(10, 5))
            plt.plot(self.equity_curve, color='purple', label='Equity Curve (Smart Trailing)')
            plt.axhline(y=5000, color='red', linestyle='--', label='Initial Balance')
            plt.title(f"SMC AI Backtest (Smart Trail 1:1 RR): {self.symbol}")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(f"smc_ai_trading_system/backtest_equity_{self.symbol}.png")
            print(f"Equity Curve saved: smc_ai_trading_system/backtest_equity_{self.symbol}.png")
        
        except Exception as e:
            print(f"[ERROR] Backtest failed: {e}")

if __name__ == "__main__":
    DATA_DIR = "smc_ai_trading_system/data/"
    HIST_DIR = "/home/add/Desktop/Git/qlib_mql5_bot/history_data/"
    
    # Using NDX data for backtest
    D1 = DATA_DIR + "NDXUSD.p_D1.csv"
    H1 = DATA_DIR + "NDXUSD.p_H1.csv"
    M15 = DATA_DIR + "NDXUSD.p_M15.csv"
    
    backtester = SMCBacktester(symbol="NDXUSD.p")
    backtester.run_backtest(D1, H1, M15)
