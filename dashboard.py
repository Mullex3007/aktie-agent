import os
import json
from flask import Flask, render_template_string
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from collections import defaultdict
from datetime import datetime

load_dotenv()
app = Flask(__name__)
alpaca_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

SEKTOR_MAP = {
    "JPM": "Finans", "BAC": "Finans", "GS": "Finans", "MS": "Finans",
    "C": "Finans", "WFC": "Finans", "AXP": "Finans", "USB": "Finans",
    "TFC": "Finans", "BLK": "Finans", "PGR": "Forsikring",
    "PRU": "Forsikring", "AFL": "Forsikring", "ALL": "Forsikring",
    "CB": "Forsikring", "HIG": "Forsikring", "AON": "Forsikring",
    "CVX": "Energi", "XOM": "Energi", "BP": "Energi", "SHEL": "Energi",
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "AMZN": "Tech",
    "META": "Tech", "NVDA": "Tech", "ABT": "Sundhed", "PFE": "Sundhed",
    "NVO": "Sundhed", "GMAB": "Sundhed", "BMY": "Sundhed"
}

def beregn_hit_rate_over_tid(handler):
    daglige = defaultdict(lambda: {"positive": 0, "total": 0})
    for h in handler:
        if h["udfald"] == "afventer":
            continue
        dato = h["dato"][:10]
        daglige[dato]["total"] += 1
        if "\u2705" in h["udfald"]:
            daglige[dato]["positive"] += 1
    datoer = sorted(daglige.keys())
    hit_rates = []
    total_pos = 0
    total_alle = 0
    for dato in datoer:
        total_pos += daglige[dato]["positive"]
        total_alle += daglige[dato]["total"]
        rate = round(total_pos / total_alle * 100, 1) if total_alle > 0 else 0
        hit_rates.append(rate)
    return datoer, hit_rates


def beregn_sektor_detaljer(positioner):
    sektorer = defaultdict(list)
    for p in positioner:
        sektor = SEKTOR_MAP.get(p.symbol, 'Andre')
        sektorer[sektor].append(p.symbol)
    resultat = []
    for sektor in sorted(sektorer.keys()):
        for ticker in sorted(sektorer[sektor]):
            resultat.append((sektor, ticker))
    return resultat

def beregn_sektor_fordeling(handler):
    sektorer = defaultdict(int)
    for h in handler:
        sektor = SEKTOR_MAP.get(h["ticker"], "Andre")
        sektorer[sektor] += 1
    sorteret = sorted(sektorer.items(), key=lambda x: x[0])
    return [s[0] for s in sorteret[:6]], [s[1] for s in sorteret[:6]]

@app.route("/")
def index():
    konto = alpaca_client.get_account()
    positioner = alpaca_client.get_all_positions()
    handler = []
    if os.path.exists("handler_log.json"):
        with open("handler_log.json") as f:
            handler = json.load(f)
    med_udfald = [h for h in handler if h["udfald"] != "afventer"]
    positive = len([h for h in med_udfald if "\u2705" in h["udfald"]])
    negative = len([h for h in med_udfald if "\u274c" in h["udfald"]])
    hit_rate = round(positive / len(med_udfald) * 100) if med_udfald else 0
    hit_farve = "#1565c0"
    datoer, hit_rates = beregn_hit_rate_over_tid(handler)
    sektor_labels, sektor_data = beregn_sektor_fordeling(handler)
    html = open("dashboard_html.html").read()
    return render_template_string(html,
        konto=konto, positioner=positioner,
        seneste_handler=list(reversed(handler[-10:])),
        total_handler=len(handler), positive=positive, negative=negative,
        hit_rate=hit_rate, hit_farve=hit_farve, datoer=datoer,
        hit_rates=hit_rates, sektor_labels=sektor_labels, sektor_data=sektor_data, sektor_liste=sorted(zip(sektor_labels, sektor_data)), sektor_detaljer=beregn_sektor_detaljer(positioner),
        portfolio_value=f"{float(konto.portfolio_value):,.0f}",
        cash=f"{float(konto.cash):,.0f}",
        aktive_positioner=len(positioner),
        tidspunkt=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route("/koer-agent")
def koer_agent_route():
    os.system("python3 aktie_agent.py &")
    return "<script>alert('AGENT STARTET'); window.location='/';</script>"

if __name__ == "__main__":
    app.run(debug=False, port=5001, host="0.0.0.0")
