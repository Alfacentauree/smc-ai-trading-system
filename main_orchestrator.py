import pandas as pd
import time
import shutil
import os
import sys
import json
import csv
from datetime import datetime
from macro_engine import MacroEngine
from liquidity_sweep import LiquiditySweepDetector, load_data
from zmq_client import ZMQBridge

class SMCAISystem:
    def __init__(self, symbol, risk_percent=0.01, dry_run=True, max_spread=300):
        self.symbol = symbol
        self.risk_percent = risk_percent
        self.dry_run = dry_run
        self.max_spread = max_spread
        self.bridge = ZMQBridge(port=5558)
        self.macro = MacroEngine()
        self.detector = LiquiditySweepDetector(fractal_window=2, macro_engine=self.macro)
        self.mt5_files_path = os.path.expanduser("~/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files")
        self.local_data_path = "smc_ai_trading_system/data"
        self.last_train_time = 0
        self.last_scan_times = {} # symbol -> last_scan_timestamp
        self.active_trades_meta = {} # ticket -> {initial_risk, peak_price, be_triggered}
        os.makedirs(self.local_data_path, exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    def graceful_exit(self):
        """Safely exits the script without killing trades."""
        print("\n[SYSTEM] Shutting down orchestrator. Active trades will remain open in MT5.")
        sys.exit(0)

    def emergency_stop(self):
        """Kills all active trades and exits. (Manual trigger only)"""
        print("\n[KILL SWITCH] EMERGENCY STOP TRIGGERED!")
        if self.dry_run:
            print("[KILL SWITCH] Dry Run mode: No real trades to close.")
        else:
            print("[KILL SWITCH] Sending CLOSE_ALL command to MT5...")
            resp = self.bridge.send_order(action="CLOSE_ALL", symbol=self.symbol, lot=0.0)
            print(f"[KILL SWITCH] MT5 Response: {resp}")
        print("[KILL SWITCH] System shutdown complete.")
        sys.exit(0)

    def sync_data_from_mt5(self):
        print(f"\n[SYNC] Requesting latest data for {self.symbol} from MT5...")
        self.bridge.send_order(action="SYNC_DATA", symbol=self.symbol, lot=0.0)
        time.sleep(3)
        tfs = ["H1", "M15", "M1"]
        paths = []
        for tf in tfs:
            src = f"{self.mt5_files_path}/{self.symbol}_{tf}.csv"
            dst = f"{self.local_data_path}/{self.symbol}_{tf}.csv"
            if os.path.exists(src):
                shutil.copy(src, dst)
                paths.append(dst)
            else:
                paths.append(dst)
        return paths

    def get_account_status(self):
        """Returns balance and spread from MT5."""
        try:
            response = self.bridge.send_order(action="ACCOUNT_INFO", symbol=self.symbol, lot=0.0)
            if response.get("status") == "success":
                return float(response.get("balance", 0.0)), int(response.get("spread", 999))
            return 0.0, 999
        except Exception as e:
            print(f"[ERROR] Failed to get account status: {e}")
            return 0.0, 999

    def log_trade(self, action, entry, sl, lot, h1_bias, m15_bias, reason):
        log_file = "logs/trade_journal.csv"
        file_exists = os.path.isfile(log_file)
        with open(log_file, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Symbol", "Action", "Entry", "SL", "Lot", "H1_Bias", "M15_Bias", "Reason"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.symbol, action, entry, sl, lot, 
                f"{h1_bias*100:.1f}%", f"{m15_bias*100:.1f}%", reason
            ])

    def log_bias(self, h1_bias, m15_bias, timestamp):
        """Logs AI Bias to a CSV file for tracking."""
        log_file = "logs/bias_log.csv"
        file_exists = os.path.isfile(log_file)
        with open(log_file, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Symbol", "H1_Prob", "M15_Prob"])
            writer.writerow([
                timestamp,
                self.symbol,
                f"{h1_bias*100:.1f}%",
                f"{m15_bias*100:.1f}%"
            ])
        print(f"[AI BIAS LOGGED] {self.symbol} | H1: {h1_bias*100:.1f}% | M15: {m15_bias*100:.1f}%")

    def get_active_positions(self):
        """Returns list of active positions from MT5."""
        try:
            response = self.bridge.send_order(action="GET_POSITIONS", symbol=self.symbol, lot=0.0)
            if response.get("status") == "success":
                return response.get("positions", [])
            return []
        except Exception as e:
            print(f"[ERROR] Failed to get positions: {e}")
            return []

    def manage_trailing_sl(self):
        """Updates trailing SL for all active positions based on Smart Trail logic."""
        positions = self.get_active_positions()
        if not positions:
            self.active_trades_meta = {} # Clear cache if no trades
            return

        for pos in positions:
            ticket = str(pos['ticket'])
            entry = float(pos['entry'])
            current_sl = float(pos['sl'])
            current_price = float(pos['current_price'])
            pos_type = int(pos['type']) # 0 for BUY, 1 for SELL

            # Initialize meta if missing
            if ticket not in self.active_trades_meta:
                initial_risk = abs(entry - current_sl)
                if initial_risk == 0: continue
                self.active_trades_meta[ticket] = {
                    'initial_risk': initial_risk,
                    'peak_price': current_price,
                    'be_triggered': abs(current_price - entry) >= initial_risk
                }
            
            meta = self.active_trades_meta[ticket]
            risk = meta['initial_risk']
            new_sl = current_sl
            modified = False

            if pos_type == 0: # BUY
                if current_price > meta['peak_price']: meta['peak_price'] = current_price
                if not meta['be_triggered'] and (meta['peak_price'] - entry) >= risk:
                    meta['be_triggered'] = True
                    new_sl = entry
                    modified = True
                if meta['be_triggered']:
                    trail_level = meta['peak_price'] - risk
                    if trail_level > new_sl:
                        new_sl = trail_level
                        modified = True
            else: # SELL
                if current_price < meta['peak_price']: meta['peak_price'] = current_price
                if not meta['be_triggered'] and (entry - meta['peak_price']) >= risk:
                    meta['be_triggered'] = True
                    new_sl = entry
                    modified = True
                if meta['be_triggered']:
                    trail_level = meta['peak_price'] + risk
                    if trail_level < new_sl:
                        new_sl = trail_level
                        modified = True

            if modified and abs(new_sl - current_sl) > 0.00001:
                print(f"[{'DRY RUN' if self.dry_run else 'LIVE'}] Modifying SL for Ticket {ticket}: {current_sl:.5f} -> {new_sl:.5f}")
                if not self.dry_run:
                    self.bridge.send_order(action="MODIFY_SL", symbol=self.symbol, lot=0.0, ticket=int(ticket), sl=new_sl, tp=0.0)

    def calculate_lot_size(self, balance, entry, stop_loss):
        risk_amount = balance * self.risk_percent
        sl_distance = abs(entry - stop_loss)
        if sl_distance == 0: return 0.1, 0, 0
        
        # --- Contract Size Logic ---
        if "BTC" in self.symbol or "XAU" in self.symbol:
            # BTC/Gold: 1 point = 1 unit
            raw_lot = risk_amount / sl_distance
            min_floor = 0.01 if "XAU" in self.symbol else 0.1
        elif "NDX" in self.symbol or "US30" in self.symbol:
            # Indices: 1 point = 1 unit (most brokers)
            raw_lot = risk_amount / sl_distance
            min_floor = 0.1 # Indices usually require min 0.1
        else:
            # Forex/Other: Standard multiplier
            raw_lot = risk_amount / (sl_distance * 100)
            min_floor = 0.01

        final_lot = round(max(min_floor, min(raw_lot, 5.0)), 2)
        return final_lot, sl_distance, risk_amount

    def run_live_cycle(self):
        try:
            # 1. News Pause Check (Manual switch: file 'PAUSE' in root)
            if os.path.exists("PAUSE"):
                print("[NEWS] System PAUSED. Remove 'PAUSE' file to resume.")
                time.sleep(60)
                return

            # 2. Trailing SL Management
            self.manage_trailing_sl()

            # 3. AI Scan (Every 1 minute per symbol for M1 Entry)
            current_time = time.time()
            last_scan = self.last_scan_times.get(self.symbol, 0)
            
            if current_time - last_scan < 60:
                return
            
            self.last_scan_times[self.symbol] = current_time
            h1_file, m15_file, m1_file = self.sync_data_from_mt5()
            print(f"\n--- Starting SMC AI Scan for {self.symbol} (DRY RUN: {self.dry_run}) ---")
            
            # AI Probability Logic: Update bias cache using latest synced data
            self.macro.update_bias_cache(h1_file, m15_file)
            
            df_1m = load_data(m1_file)
            df_1m = self.detector.identify_fractals(df_1m)
            latest_ts = df_1m.index[-1]
            h1_bias, m15_bias = self.macro.get_bias(latest_ts)
            
            # Log bias to file and console
            self.log_bias(h1_bias, m15_bias, latest_ts)
            
            # Adjusted thresholds: H1 (HTF) = 60%, M15 (LTF) = 50%
            signals = self.detector.detect_sweeps(df_1m, htf_threshold=0.6, ltf_threshold=0.5)
            
            # Data Freshness Check (Accounting for Timezone Offset)
            # Use the latest candle as the 'current' market time
            market_time = df_1m.index[-1]
            system_now = datetime.now()
            
            # Simple offset calculation: 
            # If the gap is > 5 mins, we'll just log the offset once and use it.
            # For now, we compare latest candle vs signal time, which is already relative.
            
            if signals.empty:
                print(f"[LOG] {self.symbol}: No valid AI-confirmed setups found in history.")
                return

            latest_signal = signals.iloc[-1]
            signal_time = pd.to_datetime(latest_signal['time'])
            
            # Use data-relative time instead of system-relative time
            time_diff = market_time - signal_time
            
            print(f"[STATUS] Latest Candle: {market_time} | Latest Signal: {signal_time} (Diff: {time_diff.total_seconds()/60:.1f} min)")

            if time_diff.total_seconds() > 180: # Signal within last 3 minutes of data (M1)
                print(f"[LOG] Latest signal ({latest_signal['type']}) is too old. Waiting for new setup.")
                return

            # 4. Spread & Balance Filter
            balance, current_spread = self.get_account_status()
            if current_spread > self.max_spread:
                print(f"[FILTER] Spread too high: {current_spread} (Max: {self.max_spread}). Skipping.")
                return
            if balance == 0: return

            if len(self.get_active_positions()) > 0:
                print(f"[LOG] Active trade already exists. Skipping.")
                return

            lot, sl_pts, risk = self.calculate_lot_size(balance, latest_signal['entry'], latest_signal['stop_loss'])
            
            # --- SPREAD VS SL CHECK ---
            # If sl_distance in points < spread * 1.5, MT5 will likely reject it.
            # Convert risk to points (approximate for crypto/indices)
            risk_in_points = risk / (0.01 if "BTC" in self.symbol else 100)
            
            print(f"\n--- SIGNAL DETECTED ---")
            print(f"Type: {latest_signal['type']} | Spread: {current_spread}")
            print(f"Entry: {latest_signal['entry']:.5f} | SL: {latest_signal['stop_loss']:.5f} | Lot: {lot}")
            print(f"Risk Points: {risk_in_points:.1f} vs Spread: {current_spread}")

            if risk_in_points < (current_spread * 1.2):
                print(f"[FILTER] SL too tight for current spread ({risk_in_points:.1f} < {current_spread * 1.2}). Skipping.")
                return

            action = "BUY" if "BULLISH" in latest_signal['type'] else "SELL"
            payload = {
                "action": action, "symbol": self.symbol, "lot": 0.01 if self.dry_run else lot, 
                "sl": round(latest_signal['stop_loss'], 5), "tp": 0.0, "comment": "SMC_AI_BOT"
            }

            if self.dry_run:
                print(f"[DRY RUN] Would execute: {payload}")
            else:
                print(f"[LIVE] Executing {action}...")
                resp = self.bridge.send_order(**payload)
                if resp.get("status") == "success":
                    self.log_trade(action, latest_signal['entry'], latest_signal['stop_loss'], lot, h1_bias, m15_bias, latest_signal['type'])
                print(f"Response: {resp}")
        
        except Exception as e:
            print(f"[CRITICAL ERROR] {e}")

if __name__ == "__main__":
    # --- MULTI-SYMBOL CONFIGURATION ---
    SYMBOLS = ["BTCUSD.p", "NDXUSD.p"]  # Aap yahan aur bhi assets add kar sakte hain

    # Initialize system with the first symbol (it will switch dynamically)
    system = SMCAISystem(
        symbol=SYMBOLS[0],
        risk_percent=0.0025,
        dry_run=False,
        max_spread=15000,
    )

    print("--- SMC AI ORCHESTRATOR v2.6 STARTED (Multi-Asset Mode) ---")
    print(f"Monitoring: {SYMBOLS}")

    try:
        while True:
            for current_symbol in SYMBOLS:
                # Dynamically update the symbol for the next scan
                system.symbol = current_symbol
                print(f"\n[SCAN] Checking Asset: {current_symbol}...")

                try:
                    system.run_live_cycle()
                except Exception as e:
                    print(f"[ERROR] Cycle failed for {current_symbol}: {e}")

                # Small gap between assets to avoid ZMQ congestion
                time.sleep(5)

            # Wait 10 seconds before starting the next full loop
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n[STOP] Exiting gracefully...")

