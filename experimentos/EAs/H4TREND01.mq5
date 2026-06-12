//+------------------------------------------------------------------+
//| X1-ARCHITECT v106 | ID: H4TREND01 | LONG
//| Entrada: adx_34_sft >= 26.935992|minus_di_8_sft >= 19.712099
//| Salida : SINTETICA_REVERSE (rotura de regla, tope 48 velas) | Cooldown: 6 velas
//| SINCRONIA: senal evaluada a vela nueva con shift=2 (columnas _sft de X1:
//| la decision del motor en la vela i usa indicadores de la vela i-1).
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>
CTrade trade;

input double InpLots         = 0.10;
input long   InpMagic        = 200129895;
input int    InpCooldownBars = 6;

#define SHIFT_SIGNAL   2
#define MAX_HOLD_SYNTH 48

int h_adx_34;
int h_adx_8;

datetime g_last_bar       = 0;
datetime g_entry_bar      = 0;
datetime g_last_entry_bar = 0;

int OnInit() {
   h_adx_34 = iADX(_Symbol, _Period, 34);
   h_adx_8 = iADX(_Symbol, _Period, 8);
   if(h_adx_34 == INVALID_HANDLE) return(INIT_FAILED);
   if(h_adx_8 == INVALID_HANDLE) return(INIT_FAILED);
   trade.SetExpertMagicNumber(InpMagic);
   return(INIT_SUCCEEDED);
}

double GetVal(int handle, int buffer, int shift) {
   double buf[];
   if(CopyBuffer(handle, buffer, shift, 1, buf) > 0) return buf[0];
   return 0.0;
}


bool X1_EntryRule(int s) {
   return (GetVal(h_adx_34, 0, s) >= 26.935992) && (GetVal(h_adx_8, 2, s) >= 19.712099);
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
      if(held >= MAX_HOLD_SYNTH || !X1_EntryRule(SHIFT_SIGNAL))
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
      int h = FileOpen("X1_TRUTH_H4TREND01.csv", FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI);
      if(h != INVALID_HANDLE) {
         FileWrite(h, "Time", "Equity");
         FileWrite(h, TimeToString(TimeCurrent()), AccountInfoDouble(ACCOUNT_EQUITY));
         FileClose(h);
      }
   }
}
