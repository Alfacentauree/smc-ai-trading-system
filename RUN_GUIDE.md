# SMC AI Trading System - Execution Guide (v2.20)

This guide provides step-by-step instructions to set up and run the SMC AI Trading System, which integrates MetaTrader 5 (MT5) with a Python-based AI orchestration engine via ZeroMQ.

---

## 🛠 Prerequisites

### 1. Software Requirements
- **MetaTrader 5 (MT5):** Installed and running via **Wine** (on Linux).
- **Python 3.8+:** Installed on your system.
- **ZeroMQ (ZMQ):** Used for communication between MT5 and Python.

### 2. Python Dependencies
Install the required libraries using pip:
```bash
pip install pandas numpy pyzmq lightgbm joblib matplotlib
```

---

## 🚀 Step 1: MetaTrader 5 (MT5) Setup

1.  **Install the EA:**
    - Locate `ZMQ_Bridge_EA.mq5` in the project root.
    - Copy it to your MT5 Experts folder:
      `~/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/ZMQ_Bridge_EA.mq5`
2.  **Configure MT5:**
    - Open MT5.
    - Go to **Tools > Options > Expert Advisors**.
    - Check **"Allow Algorithmic Trading"**.
    - Check **"Allow DLL imports"** (Critical for ZMQ).
3.  **Attach the EA:**
    - Refresh the Navigator in MT5 and find `ZMQ_Bridge_EA`.
    - Drag it onto any chart (e.g., NDXUSD.p M15).
    - In the EA inputs, ensure the port is set to **5558**.

---

## 🧠 Step 2: AI Orchestrator Setup

The orchestrator manages data syncing, macro analysis, and order execution.

1.  **Verify Model Paths:**
    - Ensure your pre-trained models (`d1_lightgbm.pkl`, `h1_lightgbm.pkl`) are located in the `models/` directory.
2.  **Configuration:**
    - The system defaults to **1% Risk per trade** and a **60% probability threshold**.
    - Modify `main_orchestrator.py` if you wish to change the `symbol` or `dry_run` mode.

---

## 🏃 Step 3: Running the System

1.  **Start MT5 first:** Ensure the `ZMQ_Bridge_EA` is active (look for the "Connected" log in the MT5 Experts tab).
2.  **Launch the Orchestrator:**
    ```bash
    cd /home/add/Desktop/Git/smc_ai_trading_system
    python3 main_orchestrator.py
    ```

---

## 🕹 Features & Controls

-   **Auto-Sync:** The system automatically requests the latest H1, D1, and M15 data from MT5 on startup.
-   **Kill Switch:** If the orchestrator detects a critical error or manual intervention is needed, use `Ctrl+C` to trigger a safe shutdown. (The script is designed to handle termination gracefully).
-   **Dry Run Mode:** Set `dry_run=True` in `main_orchestrator.py` to simulate trades without sending actual orders to MT5.

---

## 📂 Project Structure
- `main_orchestrator.py`: The "brain" that coordinates everything.
- `ZMQ_Bridge_EA.mq5`: The MQL5 bridge script for MT5.
- `liquidity_sweep.py`: Detects SMC liquidity patterns.
- `macro_engine.py`: Performs higher time-frame trend analysis.
- `zmq_client.py`: Python-side communication logic.

---

**⚠️ Warning:** Trading involves significant risk. Always test in a demo account first.
