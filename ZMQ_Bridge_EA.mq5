//+------------------------------------------------------------------+
//|                                              ZMQ_Bridge_EA.mq5   |
//|                                  Copyright 2026, SMC AI Trading  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, SMC AI Trading"
#property version   "2.50"
#property strict

#include <JAson.mqh>
#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

#import "libzmq.dll"
    long zmq_ctx_new();
    int  zmq_ctx_term(long context);
    long zmq_socket(long context, int type);
    int  zmq_close(long socket);
    int  zmq_bind(long socket, uchar &endpoint[]); 
    int  zmq_recv(long socket, uchar &buf[], int len, int flags);
    int  zmq_send(long socket, uchar &buf[], int len, int flags);
    int  zmq_errno();
#import

#define ZMQ_REP 4
#define ZMQ_DONTWAIT 1

input string InpZmqAddress  = "tcp://127.0.0.1:5558";
input int    InpMagicNumber = 123456;

long context_ptr = 0;
long socket_ptr  = 0;
CTrade trade;
CPositionInfo pos_info;

int OnInit() {
   Print("ZMQ: Starting v2.50 (Trailing SL & Comments Update)...");
   
   context_ptr = zmq_ctx_new();
   if(context_ptr == 0) {
      Print("ZMQ ERROR: Context creation failed.");
      return(INIT_FAILED);
   }
   
   socket_ptr = zmq_socket(context_ptr, ZMQ_REP);
   if(socket_ptr == 0) {
      Print("ZMQ ERROR: Socket creation failed.");
      return(INIT_FAILED);
   }
   
   uchar addr_ansi[];
   StringToCharArray(InpZmqAddress, addr_ansi);
   
   int res = zmq_bind(socket_ptr, addr_ansi);
   if(res != 0) {
      int err = zmq_errno();
      Print("ZMQ ERROR: Bind failed to ", InpZmqAddress, " | Errno: ", err);
      zmq_close(socket_ptr);
      zmq_ctx_term(context_ptr);
      return(INIT_FAILED);
   }
   
   EventSetMillisecondTimer(100);
   trade.SetExpertMagicNumber(InpMagicNumber);
   Print("ZMQ SUCCESS: Bridge listening on ", InpZmqAddress);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   EventKillTimer();
   if(socket_ptr != 0) zmq_close(socket_ptr);
   if(context_ptr != 0) zmq_ctx_term(context_ptr);
}

void OnTimer() {
   uchar buffer[2048];
   ArrayInitialize(buffer, 0);
   int bytes = zmq_recv(socket_ptr, buffer, 2048, ZMQ_DONTWAIT);
   if(bytes > 0) {
      string json_str = CharArrayToString(buffer, 0, bytes);
      Print("ZMQ Received: ", json_str);
      CJAVal root;
      if(root.Deserialize(json_str)) HandleAction(root);
   }
}

void HandleAction(CJAVal &root) {
   string action = root["action"].ToStr();
   string symbol = root["symbol"].ToStr();
   
   if(action == "CLOSE_ALL") {
      int closed_count = 0;
      for(int i=PositionsTotal()-1; i>=0; i--) {
         if(pos_info.SelectByIndex(i) && pos_info.Magic() == InpMagicNumber) {
            if(trade.PositionClose(pos_info.Ticket())) closed_count++;
         }
      }
      SendResponse("success", "Closed " + (string)closed_count + " positions.");
   }
   else if(action == "SYNC_DATA") {
      ExportHistory(symbol, PERIOD_H1, symbol+"_H1.csv", 2000);
      ExportHistory(symbol, PERIOD_M15, symbol+"_M15.csv", 5000);
      ExportHistory(symbol, PERIOD_M1, symbol+"_M1.csv", 10000);
      SendResponse("success", "Data exported");
   }
   else if(action == "ACCOUNT_INFO") {
      CJAVal resp;
      resp["status"] = "success";
      resp["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
      resp["spread"] = (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
      SendResponse(resp);
   }
   else if(action == "GET_POSITIONS") {
      CJAVal resp;
      resp["status"] = "success";
      CJAVal positions;
      int count = 0;
      for(int i=PositionsTotal()-1; i>=0; i--) {
         if(PositionGetSymbol(i) == symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) {
            CJAVal pos;
            pos["ticket"] = PositionGetInteger(POSITION_TICKET);
            pos["type"] = PositionGetInteger(POSITION_TYPE);
            pos["entry"] = PositionGetDouble(POSITION_PRICE_OPEN);
            pos["sl"] = PositionGetDouble(POSITION_SL);
            pos["tp"] = PositionGetDouble(POSITION_TP);
            pos["current_price"] = PositionGetDouble(POSITION_PRICE_CURRENT);
            positions.Add(pos);
            count++;
         }
      }
      resp["positions"] = positions;
      resp["count"] = count;
      SendResponse(resp);
   }
   else if(action == "MODIFY_SL") {
      long ticket = (long)root["ticket"].ToInt();
      double sl = root["sl"].ToDbl();
      double tp = root["tp"].ToDbl();
      bool res = trade.PositionModify(ticket, sl, tp);
      SendResponse(res ? "success" : "error", res ? "Modified SL" : trade.ResultRetcodeDescription());
   }
   else if(action == "BUY" || action == "SELL") {
      ExecuteTrade(root);
   }
}

void ExportHistory(string sym, ENUM_TIMEFRAMES tf, string filename, int count) {
   int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, '\t');
   if(handle != INVALID_HANDLE) {
      FileWrite(handle, "<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<TICKVOL>", "<VOL>", "<SPREAD>");
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      int copied = CopyRates(sym, tf, 0, count, rates);
      for(int i=copied-1; i>=0; i--) {
         FileWrite(handle, 
            TimeToString(rates[i].time, TIME_DATE),
            TimeToString(rates[i].time, TIME_MINUTES),
            rates[i].open, rates[i].high, rates[i].low, rates[i].close,
            rates[i].tick_volume, rates[i].real_volume, rates[i].spread
         );
      }
      FileClose(handle);
   }
}

void ExecuteTrade(CJAVal &root) {
   string action = root["action"].ToStr();
   string symbol = root["symbol"].ToStr();
   double lot = root["lot"].ToDbl();
   double sl = root["sl"].ToDbl();
   double tp = root["tp"].ToDbl();
   string comment = root["comment"].ToStr();
   if(comment == "") comment = "SMC_AI_BOT";
   
   // Normalize Volume (Lot)
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   lot = MathMax(min_lot, MathMin(max_lot, lot));
   lot = MathFloor(lot / step_lot) * step_lot;
   
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(sl > 0) sl = NormalizeDouble(sl, digits);
   if(tp > 0) tp = NormalizeDouble(tp, digits);
   
   // Deviation of 10 points for more reliable execution
   bool res = (action == "BUY") ? trade.Buy(lot, symbol, 0, sl, tp, comment) : trade.Sell(lot, symbol, 0, sl, tp, comment);
   if (!res) {
       res = (action == "BUY") ? trade.Buy(lot, symbol, 10, sl, tp, comment) : trade.Sell(lot, symbol, 0, sl, tp, comment);
   }
   
   SendResponse(res ? "success" : "error", res ? "Placed" : trade.ResultRetcodeDescription());
}

void SendResponse(string status, string message) {
   CJAVal resp; resp["status"] = status; resp["message"] = message;
   SendResponse(resp);
}

void SendResponse(CJAVal &resp) {
   string resp_str = resp.Serialize();
   uchar buf[]; StringToCharArray(resp_str, buf);
   zmq_send(socket_ptr, buf, ArraySize(buf)-1, 0);
}
