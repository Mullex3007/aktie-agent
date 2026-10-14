import os
import json
from flask import Flask, render_template_string
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from collections import defaultdict
from datetime import datetime, timedelta
from anthropic import Anthropic

load_dotenv()

app = Flask(__name__)

alpaca_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SEKTOR_MAP = {
    "JPM": "Finans", "BAC": "Finans", "GS": "Finans", "C": "Finans",
    "WFC": "Finans", "AXP": "Finans", "USB": "Finans", "TFC": "Finans",
    "BLK": "Finans", "BK": "Finans", "PGR": "Forsikring", "PRU": "Forsikring",
    "AFL": "Forsikring", "ALL": "Forsikring", "CB": "Forsikring",
    "HIG": "Forsikring", "AON": "Forsikring", "MMC": "Forsikring",
    "AIG": "Forsikring", "CVX": "Energi", "XOM": "Energi", "BP": "Energi",
    "SHEL": "Energi", "COP": "Energi", "EOG": "Energi", "SLB": "Energi",
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "AMZN": "Tech",
    "META": "Tech", "NVDA": "Tech", "AMD": "Tech", "ADBE": "Tech",
    "ABT": "Sundhed", "PFE": "Sundhed", "JNJ": "Sundhed", "UNH": "Sundhed",
    "NVO": "Sundhed", "GMAB": "Sundhed", "BMY": "Sundhed", "AMGN": "Sundhed",
    "MRNA": "Sundhed", "UBER": "Tech", "LYFT": "Tech"
}

uge_konklusion_cache = {"tekst": "", "dato": ""}

def generer_uge_konklusion(handler):
    global uge_konklusion_cache
    i_dag = datetime.now().strftime("%Y-%m-%d")
    if uge_konklusion_cache["dato"] == i_dag and uge_konklusion_cache["tekst"]:
        return uge_konklusion_cache["tekst"]

    uge_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    uge_handler = [h for h in handler if h["dato"][:10] >= uge_start]
    med_udfald = [h for h in uge_handler if h["udfald"] != "afventer"]

    if not med_udfald:
        return "Ingen afsluttede handler denne uge endnu."

    wins = [h for h in med_udfald if "\u2705" in h["udfald"]]
    losses = [h for h in med_udfald if "\u274c" in h["udfald"]]
    hit_rate = round(len(wins) / len(med_udfald) * 100) if med_udfald else 0

    prompt = f"""
Du er en kvantitativ porteføljemanager. Skriv en MEGET kort ugentlig konklusion på dansk.
Max 2 sætninger. Vær direkte og datadriven. Ingen floskler.

Ugens data:
- {len(med_udfald)} handler med udfald
- {len(wins)} wins, {len(losses)} losses
- Hit rate: {hit_rate}%
- Bedste handler: {', '.join([h['ticker'] for h in wins[:3]])}
- Dårligste handler: {', '.join([h['ticker'] for h in losses[:3]])}

Returner KUN de 2 sætninger, ingen JSON, ingen forklaring.
"""
    try:
        besked = anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        tekst = besked.content[0].text.strip()
        uge_konklusion_cache = {"tekst": tekst, "dato": i_dag}
        return tekst
    except:
        return f"Denne uge: {len(med_udfald)} handler med {hit_rate}% hit rate. {len(wins)} wins og {len(losses)} losses."

def beregn_statistik(handler):
    med_udfald = [h for h in handler if h["udfald"] != "afventer"]
    wins = []
    losses = []
    for h in med_udfald:
        try:
            pct_str = h["udfald"].replace("+", "").replace("%", "").strip()
            for tegn in ["\u2705", "\u274c", " "]:
                pct_str = pct_str.replace(tegn, "")
            pct = float(pct_str.strip())
            if "\u2705" in h["udfald"]:
                wins.append(pct)
            else:
                losses.append(pct)
        except:
            pass
    positive = len(wins)
    negative = len(losses)
    hit_rate = round(positive / len(med_udfald) * 100) if med_udfald else 0
    snit_gevinst = round(sum(wins) / len(wins), 2) if wins else 0
    snit_tab = round(sum(losses) / len(losses), 2) if losses else 0
    risk_reward = round(abs(snit_gevinst / snit_tab), 2) if snit_tab != 0 else 0
    return positive, negative, hit_rate, snit_gevinst, snit_tab, risk_reward

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

def beregn_sektor_positioner(positioner):
    sektorer = defaultdict(int)
    for p in positioner:
        sektor = SEKTOR_MAP.get(p.symbol, "Andre")
        sektorer[sektor] += 1
    sorteret = sorted(sektorer.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in sorteret], [s[1] for s in sorteret]

@app.route("/")
def index():
    konto = alpaca_client.get_account()
    positioner = alpaca_client.get_all_positions()
    handler = []
    if os.path.exists("handler_log.json"):
        with open("handler_log.json") as f:
            handler = json.load(f)

    positive, negative, hit_rate, snit_gevinst, snit_tab, risk_reward = beregn_statistik(handler)
    hit_farve = "#2e7d32" if hit_rate >= 55 else "#e65100" if hit_rate >= 45 else "#c62828"
    rr_farve = "#2e7d32" if risk_reward >= 1 else "#e65100" if risk_reward >= 0.8 else "#c62828"
    datoer, hit_rates = beregn_hit_rate_over_tid(handler)
    sektor_labels, sektor_data = beregn_sektor_positioner(positioner)
    uge_konklusion = generer_uge_konklusion(handler)

    html = open("dashboard_html.html").read()
    return render_template_string(html,
        konto=konto, positioner=positioner,
        seneste_handler=list(reversed(handler[-10:])),
        total_handler=len(handler),
        positive=positive, negative=negative,
        hit_rate=hit_rate, hit_farve=hit_farve,
        snit_gevinst=snit_gevinst, snit_tab=snit_tab,
        risk_reward=risk_reward, rr_farve=rr_farve,
        datoer=datoer, hit_rates=hit_rates,
        sektor_labels=sektor_labels, sektor_data=sektor_data,
        portfolio_value=f"{float(konto.portfolio_value):,.0f}",
        cash=f"{float(konto.cash):,.0f}",
        aktive_positioner=len(positioner),
        tidspunkt=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        uge_konklusion=uge_konklusion
    )

@app.route("/koer-agent")
def koer_agent_route():
    os.system("python3 aktie_agent.py &")
    return "<script>alert('AGENT STARTET'); window.location='/';</script>"

if __name__ == "__main__":
    app.run(debug=False, port=5001, host="0.0.0.0")