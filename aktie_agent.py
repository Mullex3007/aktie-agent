import os
import time
import json
import finnhub
import anthropic
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from dotenv import load_dotenv
from email_notifikation import send_email
from datetime import datetime
from screening import screen_aktier, ALLE_AKTIER
from strategi import hent_strategi
from sektorer import sektor_for

load_dotenv()

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
alpaca_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

AKTIER = ["CVX", "BP", "SHEL", "XOM", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "JPM", "BAC", "GS", "C", "WFC", "BLK", "AXP", "USB", "TFC", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "SAP", "ASML", "TSM", "ABT", "PFE", "JNJ", "UNH", "MRK", "ABBV", "TMO", "DHR", "BMY", "AMGN", "DIS", "UBER", "SBUX", "KO", "WMT", "COST", "TGT", "CAT", "DE", "HON", "GE", "MMM", "UPS", "FDX", "BA", "LMT", "RTX", "NVO", "TM", "BABA", "SONY", "BRK-B", "V", "MA", "TXN"]
LOG_FIL = "handler_log.json"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

def hent_aktiedata(ticker):
    try:
        quote = finnhub_client.quote(ticker)
        metrics = finnhub_client.company_basic_financials(ticker, 'all')
        m = metrics.get('metric', {})
        return {
            "ticker": ticker,
            "navn": ticker,
            "pris": quote.get("c", 0),
            "pe_ratio": m.get("peTTM", None),
            "pb_ratio": m.get("pbQuarterly", None),
            "52_ugers_høj": m.get("52WeekHigh", 0),
            "52_ugers_lav": m.get("52WeekLow", 0),
            "markedsværdi": m.get("marketCapitalization", 0),
        }
    except Exception as e:
        print(f"Fejl ved hentning af {ticker}: {e}")
        return None

def hent_tidligere_handler():
    if os.path.exists(LOG_FIL):
        with open(LOG_FIL, "r") as f:
            return json.load(f)
    return []

def gem_handel(handel):
    handler = hent_tidligere_handler()
    handler.append(handel)
    with open(LOG_FIL, "w") as f:
        json.dump(handler, f, indent=2)

def er_allerede_handlet_i_dag(ticker):
    """Tjekker om aktien allerede er handlet i dag"""
    handler = hent_tidligere_handler()
    i_dag = datetime.now().strftime("%Y-%m-%d")
    for h in handler:
        if h["ticker"] == ticker and h["dato"].startswith(i_dag):
            return True
    return False

def hent_aabne_positioner():
    try:
        return {p.symbol for p in alpaca_client.get_all_positions()}
    except Exception as e:
        print(f"⚠️  Kunne ikke hente positioner: {e}")
        return set()

def analyser_med_claude(aktiedata, strategi):
    tidligere_handler = hent_tidligere_handler()
    historik_tekst = ""
    if tidligere_handler:
        relevante = [h for h in tidligere_handler if h["ticker"] == aktiedata["ticker"]]
        if relevante:
            historik_tekst = f"\nTidligere handler for {aktiedata['ticker']}:\n"
            for h in relevante[-3:]:
                historik_tekst += f"- {h['dato']}: {h['anbefaling']} ved ${h['pris']}, udfald: {h.get('udfald', 'ukendt')}\n"

    prompt = f"""
Du er en elitaer AI-aktieanalytiker for en kvantitativ fond. Din opgave er at vurdere en aktie der allerede har bestaaet en indledende screening, og traffe en binaer beslutning (KOEB eller AFVENT) samt angive en praecis konfidensgrad.

<aktie_data>
{{
  "ticker": "{aktiedata['ticker']}",
  "aktuel_kurs": "{aktiedata['pris']}",
  "pe_ratio": "{aktiedata['pe_ratio']}",
  "pb_ratio": "{aktiedata['pb_ratio']}",
  "52_ugers_lav": "{aktiedata['52_ugers_lav']}",
  "52_ugers_hoej": "{aktiedata['52_ugers_høj']}",
  "afvigelse_fra_lav_pct": "{aktiedata.get('afstand_fra_lav', 'ukendt')}%"
}}
</aktie_data>

<sektor>{sektor_for(aktiedata['ticker'])}</sektor>

<traener_agentens_konklusion>
Fokussektorer: {", ".join(strategi["fokus_sektorer"]) or "ingen"}
Aktier der historisk vinder: {", ".join(strategi["fokus_aktier"]) or "ingen"}
Analyse: {strategi["analyse"][:1500] or "Ingen analyse endnu."}
</traener_agentens_konklusion>

<tidligere_handler>
{historik_tekst if historik_tekst else "Ingen tidligere handler."}
</tidligere_handler>

Returner KUN dette JSON-objekt:
{{
  "ticker": "{aktiedata['ticker']}",
  "anbefaling": "KOEB" eller "AFVENT",
  "konfidensgrad_pct": heltal mellem 0 og 100,
  "argumentation": "Kort begrundelse."
}}
"""
    try:
        besked = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        tekst = besked.content[0].text
        # Tag kun JSON-delen, selv hvis Claude skriver tekst rundt om
        start, slut = tekst.find("{"), tekst.rfind("}")
        data = json.loads(tekst[start:slut + 1])
        return {
            "anbefaling": "KØB" if data.get("anbefaling") == "KOEB" else "HOLD",
            "begrundelse": data.get("argumentation", ""),
            "konfidensgrad": int(data.get("konfidensgrad_pct", 0))
        }
    except Exception as e:
        print(f"   ⚠️  Kunne ikke analysere {aktiedata['ticker']}: {e}")
        return None

def udfør_handel(ticker, side, pris, strategi, antal=1, begrundelse=""):
    try:
        # Bracket-ordre: købet får automatisk stop-loss og take-profit hos Alpaca
        stop_pris = round(pris * (1 - strategi["stop_loss_pct"] / 100), 2)
        take_pris = round(pris * (1 + strategi["take_profit_pct"] / 100), 2)
        ordre = MarketOrderRequest(
            symbol=ticker,
            qty=antal,
            side=side,
            time_in_force=TimeInForce.GTC,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_pris),
            stop_loss=StopLossRequest(stop_price=stop_pris)
        )
        alpaca_client.submit_order(ordre)
        gem_handel({
            "dato": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ticker": ticker,
            "anbefaling": side.value.upper(),
            "pris": pris,
            "stop_loss": stop_pris,
            "take_profit": take_pris,
            "udfald": "afventer",
            "begrundelse": begrundelse
        })

        # Email sendes ikke ved hver handel - kun i månedlig rapport
        print(f"✅ Ordre udført: {side.value} {antal} stk. {ticker} (stop {stop_pris}, mål {take_pris})")
    except Exception as e:
        print(f"❌ Handelsfejl for {ticker}: {e}")

def kør_agent():
    print("🤖 Aktie-agent starter...\n")
    dagens_handler = []
    strategi = hent_strategi()
    graense = strategi["justeret_konfidensgraense"]
    print(f"📋 Strategi: P/E < {strategi['justeret_max_pe']}, konfidens >= {graense}%, "
          f"stop-loss {strategi['stop_loss_pct']}%, take-profit {strategi['take_profit_pct']}%")
    aabne = hent_aabne_positioner()

    # Kør screening først
    print("🔍 Kører screening af 200 aktier...")
    kvalificerede = screen_aktier()
    
    if not kvalificerede:
        print("❌ Ingen aktier klarede screeningen i dag.")
        send_email("🤖 Agent rapport", "Ingen aktier klarede screeningen i dag.")
        return
    
    print(f"✅ {len(kvalificerede)} aktier sendes til Claude-analyse\n")

    for aktiedata in kvalificerede:
        ticker = aktiedata["ticker"]
        # Spring over hvis allerede handlet i dag
        if er_allerede_handlet_i_dag(ticker):
            print(f"⏭️  {ticker} – allerede handlet i dag, springer over")
            continue
        if ticker in aabne:
            print(f"⏭️  {ticker} – har allerede en åben position, springer over")
            continue

        print(f"📊 Analyserer {ticker}...")
        data = aktiedata

        analyse = analyser_med_claude(data, strategi)
        if analyse is None:
            continue
        print(f"   Anbefaling: {analyse['anbefaling']}")
        print(f"   Begrundelse: {analyse['begrundelse']}")
        print(f"   Konfidensgrad: {analyse['konfidensgrad']}%")

        if analyse["konfidensgrad"] >= graense:
            if analyse['anbefaling'] == "KØB":
                udfør_handel(ticker, OrderSide.BUY, data['pris'], strategi, begrundelse=analyse['begrundelse'])
                dagens_handler.append(f"KØB {ticker} @ ${data['pris']}")
        else:
            print(f"   ⏭️  Springer over – konfidens for lav")
        print()
        time.sleep(1)

    if not dagens_handler:
        send_email("🤖 Agent daglig rapport", "Ingen handler i dag – ingen aktier opfyldte kriterierne.")

if __name__ == "__main__":
    kør_agent()
