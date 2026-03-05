# SMC AI Trading System (v2.20)

An advanced, AI-powered trading orchestration engine that implements **Smart Money Concepts (SMC)**. This system bridges **MetaTrader 5 (MT5)** with a Python-based AI core using **ZeroMQ (ZMQ)** for high-speed communication.

## 🌟 Key Features
- **SMC Liquidity Detection:** Automated identification of liquidity sweeps and market structures.
- **AI-Driven Probabilities:** Uses LightGBM models to predict trend direction with a 60% confidence threshold.
- **MT5-Python Bridge:** Low-latency execution via ZMQ on Port 5558.
- **Risk Management:** Built-in 1% Risk-per-trade rule and automatic Kill Switch.
- **Auto-Sync:** Seamlessly synchronizes H1, D1, and M15 historical data from MT5 on startup.

## 🛠 Prerequisites
- **MetaTrader 5 (MT5):** Installed (Running via Wine if on Linux).
- **Python:** 3.8+
- **ZeroMQ:** Required for the bridge communication.

## 🚀 Getting Started

### 1. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/your-username/smc-ai-trading-system.git
cd smc-ai-trading-system
pip install -r requirements.txt
```

### 2. MetaTrader 5 Setup
1. Copy `ZMQ_Bridge_EA.mq5` to your MT5 `MQL5/Experts` folder.
2. In MT5, enable **Algo Trading** and **DLL Imports**.
3. Attach the EA to any chart (e.g., NDXUSD.p M15) and set the port to **5558**.

### 3. Execution
Ensure MT5 is running with the EA attached, then start the orchestrator:
```bash
python3 main_orchestrator.py
```

## 📂 Project Structure
- `main_orchestrator.py`: Central brain for coordination and execution.
- `ZMQ_Bridge_EA.mq5`: The MQL5 bridge script for MT5 communication.
- `liquidity_sweep.py`: Core logic for detecting SMC patterns.
- `macro_engine.py`: Higher Time Frame (HTF) trend analysis engine.
- `zmq_client.py`: Python-side ZMQ implementation.
- `models/`: Pre-trained LightGBM models.

## ⚖️ License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
**⚠️ Disclaimer:** Trading involves significant risk. This system is for educational purposes. Always test on a demo account before live trading.
