//+------------------------------------------------------------------+
//| X1-ARCHITECT v106 | ID: SESIONTEST | LONG
//| Entrada: hour_sft <= 8|dow_sft >= 2|rsi_13_sft <= 35
//| Salida : tiempo fijo: 24 velas | Cooldown: 25 velas
//| SINCRONIA: senal evaluada a vela nueva con shift=2 (columnas _sft de X1:
//| la decision del motor en la vela i usa indicadores de la vela i-1).
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>
CTrade trade;

input double InpLots         = 0.10;
input long   InpMagic        = 1575259817;
input int    InpCooldownBars = 25;

#define SHIFT_SIGNAL   2
#define MAX_HOLD_SYNTH 48

int h_rsi_13;

datetime g_last_bar       = 0;
datetime g_entry_bar      = 0;
datetime g_last_entry_bar = 0;

int OnInit() {
   h_rsi_13 = iRSI(_Symbol, _Period, 13, PRICE_CLOSE);
   if(h_rsi_13 == INVALID_HANDLE) return(INIT_FAILED);
   trade.SetExpertMagicNumber(InpMagic);
   return(INIT_SUCCEEDED);
}

double GetVal(int handle, int buffer, int shift) {
   double buf[];
   if(CopyBuffer(handle, buffer, shift, 1, buf) > 0) return buf[0];
   return 0.0;
}

double X1_DOW(int s) {
   // dia de semana. L1 guarda pandas dayofweek+1 (1=Lun..5=Vie), que para
   // dias habiles coincide EXACTO con MqlDateTime.day_of_week (domingo=0).
   MqlDateTime t; TimeToStruct(iTime(_Symbol, _Period, s), t);
   return (double)t.day_of_week;
}

double X1_HOUR(int s) {
   // hora de la vela referenciada (L1: DateTime.dt.hour, broker UTC+2)
   MqlDateTime t; TimeToStruct(iTime(_Symbol, _Period, s), t);
   return (double)t.hour;
}

bool X1_EntryRule(int s) {
   return (X1_HOUR(s) <= 8) && (X1_DOW(s) >= 2) && (GetVal(h_rsi_13, 0, s) <= 35);
}

int BarsSince(datetime t) {
   if(t == 0) return 1000000;
   return iBarShift(_Symbol, _Period, t, false);
}

void OnTick() {
   // Evaluamos UNA vez por vela (X1 decide a cierre de vela)
   datetime bar_now = iTime(_Symbol, _Period, 0);
   if(bar_now == g_last_bar) return;
   g_last_bar = bar_now;

   // --- GESTION DE SALIDA ---
   if(PositionSelect(_Symbol) && PositionGetInteger(POSITION_MAGIC) == InpMagic) {
      int held = BarsSince(g_entry_bar);
      if(held >= 24)
         trade.PositionClose(_Symbol);
      return;
   }

   // --- COOLDOWN ENTRE ENTRADAS (Min_Dist_Bars del minero) ---
   if(BarsSince(g_last_entry_bar) < InpCooldownBars) return;

   // --- ENTRADA ---
   if(X1_EntryRule(SHIFT_SIGNAL)) {
      if(trade.Buy(InpLots, _Symbol)) {
         g_entry_bar = bar_now;
         g_last_entry_bar = bar_now;
      }
   }
}

void OnDeinit(const int reason) {
   if(MQLInfoInteger(MQL_TESTER)) {
      int h = FileOpen("X1_TRUTH_SESIONTEST.csv", FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI);
      if(h != INVALID_HANDLE) {
         FileWrite(h, "Time", "Equity");
         FileWrite(h, TimeToString(TimeCurrent()), AccountInfoDouble(ACCOUNT_EQUITY));
         FileClose(h);
      }
   }
}
