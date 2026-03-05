import zmq
import json
import time

class ZMQBridge:
    def __init__(self, host="127.0.0.1", port=5558):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{host}:{port}")
        print(f"Connected to ZMQ Server at tcp://{host}:{port}")

    def send_order(self, action, symbol, lot, sl=0.0, tp=0.0, comment="", **kwargs):
        """
        Sends a trade command to MT5.
        action: 'BUY', 'SELL', 'MODIFY_SL', 'CLOSE_ALL', 'GET_POSITIONS', 'ACCOUNT_INFO', 'SYNC_DATA'
        """
        payload = {
            "action": action,
            "symbol": symbol,
            "lot": float(lot),
            "sl": float(sl),
            "tp": float(tp),
            "comment": comment,
            "timestamp": int(time.time())
        }
        
        # Add any extra fields (like 'ticket' for MODIFY_SL)
        payload.update(kwargs)
        
        message = json.dumps(payload)
        
        self.socket.send_string(message)
        
        # Wait for MT5 response
        response = self.socket.recv_string()
        return json.loads(response)

if __name__ == "__main__":
    # Test Connection
    bridge = ZMQBridge(port=5558)
    # Using BTCUSD.p as it trades 24/7 on weekends
    # We set SL/TP to 0 for a simple market order test
    result = bridge.send_order(action="BUY", symbol="BTCUSD.p", lot=0.01, sl=0.0, tp=0.0)
    print("Test Complete.")
