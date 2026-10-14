import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
from strategi import hent_strategi

load_dotenv()

alpaca_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

def beskyt_positioner():
    """Giver alle åbne positioner uden salgsordre en stop-loss og take-profit (OCO-ordre)"""
    strategi = hent_strategi()
    sl, tp = strategi["stop_loss_pct"], strategi["take_profit_pct"]
    print(f"🛡️  Beskytter positioner: stop-loss {sl}%, take-profit {tp}%\n")

    aabne_ordrer = alpaca_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
    har_salgsordre = {o.symbol for o in aabne_ordrer if o.side == OrderSide.SELL}

    beskyttet = 0
    for p in alpaca_client.get_all_positions():
        if p.symbol in har_salgsordre:
            print(f"⏭️  {p.symbol} – har allerede en salgsordre")
            continue
        antal = int(float(p.qty_available or p.qty))
        if antal <= 0:
            continue

        købspris = float(p.avg_entry_price)
        kurs = float(p.current_price)
        stop_pris = round(købspris * (1 - sl / 100), 2)
        take_pris = round(købspris * (1 + tp / 100), 2)
        # Ligger kursen allerede uden for grænserne, regnes de fra dagens kurs i stedet
        if kurs <= stop_pris:
            stop_pris = round(kurs * (1 - sl / 100), 2)
        if kurs >= take_pris:
            take_pris = round(kurs * 1.01, 2)

        try:
            alpaca_client.submit_order(LimitOrderRequest(
                symbol=p.symbol,
                qty=antal,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.OCO,
                limit_price=take_pris,
                take_profit=TakeProfitRequest(limit_price=take_pris),
                stop_loss=StopLossRequest(stop_price=stop_pris)
            ))
            beskyttet += 1
            print(f"✅ {p.symbol}: {antal} stk., købt {købspris}, stop {stop_pris}, mål {take_pris}")
        except Exception as e:
            print(f"❌ {p.symbol}: {e}")

    print(f"\n🛡️  {beskyttet} positioner fik stop-loss og take-profit.")

if __name__ == "__main__":
    beskyt_positioner()
