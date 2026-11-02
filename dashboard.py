import os
import re
import json
import subprocess
import sys
from flask import Flask, render_template_string, redirect
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from collections import defaultdict
from datetime import datetime, timedelta

load_dotenv()
app = Flask(__name__)
alpaca_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

try:
    from sektorer import sektor_for
except ImportError:
    # Før opdateringen fra 14. oktober findes sektorer.py ikke endnu
    _GAMMEL_MAP = {
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

    def sektor_for(ticker):
        return _GAMMEL_MAP.get(ticker, "Andre")

STANDARD_MAAL = 60


def laes_json(fil, standard):
    try:
        with open(fil) as f:
            return json.load(f)
    except (OSError, ValueError):
        return standard


def afkast_pct(udfald):
    m = re.search(r"([+-]?\d+(?:[.,]\d+)?)\s*%", udfald or "")
    return float(m.group(1).replace(",", ".")) if m else None


def er_vinder(h):
    return "✅" in h["udfald"]


def afgjorte(handler):
    return [h for h in handler if h.get("udfald", "afventer") != "afventer"]


def hit_rate(handler):
    return round(sum(er_vinder(h) for h in handler) / len(handler) * 100) if handler else 0


def beregn_hit_rate_over_tid(handler):
    """Samlet hit rate og rullende 30-dages hit rate for hver handelsdag."""
    pr_dag = defaultdict(list)
    for h in afgjorte(handler):
        pr_dag[h["dato"][:10]].append(er_vinder(h))
    datoer = sorted(pr_dag)
    samlet, rullende = [], []
    pos = alle = 0
    for i, dato in enumerate(datoer):
        pos += sum(pr_dag[dato])
        alle += len(pr_dag[dato])
        samlet.append(round(pos / alle * 100, 1))
        graense = (datetime.strptime(dato, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
        vindue = [v for d in datoer[:i + 1] if d > graense for v in pr_dag[d]]
        rullende.append(round(sum(vindue) / len(vindue) * 100, 1) if len(vindue) >= 10 else None)
    return datoer, samlet, rullende


def beregn_sektor_hit_rate(handler):
    stats = defaultdict(lambda: [0, 0])
    for h in afgjorte(handler):
        s = stats[sektor_for(h["ticker"])]
        s[0] += er_vinder(h)
        s[1] += 1
    rækker = [{"sektor": k, "hit_rate": round(v[0] / v[1] * 100), "antal": v[1]}
              for k, v in stats.items() if v[1] >= 5]
    return sorted(rækker, key=lambda r: -r["hit_rate"])


def beregn_positioner(positioner):
    rækker = []
    for p in positioner:
        vaerdi = float(p.market_value or 0)
        rækker.append({
            "ticker": p.symbol,
            "sektor": sektor_for(p.symbol),
            "antal": float(p.qty),
            "vaerdi": vaerdi,
            "afkast_pct": float(p.unrealized_plpc or 0) * 100,
            "afkast_kr": float(p.unrealized_pl or 0),
        })
    rækker.sort(key=lambda r: -r["vaerdi"])
    total = sum(r["vaerdi"] for r in rækker) or 1
    for r in rækker:
        r["andel"] = r["vaerdi"] / total * 100
    pr_sektor = defaultdict(float)
    for r in rækker:
        pr_sektor[r["sektor"]] += r["vaerdi"]
    for r in rækker:
        r["andel_sektor"] = r["vaerdi"] / (pr_sektor[r["sektor"]] or 1) * 100
    sektorer = sorted(pr_sektor.items(), key=lambda x: -x[1])
    sektor_fordeling = []
    for s, v in sektorer:
        medlemmer = [r for r in rækker if r["sektor"] == s]
        afkast_kr = sum(r["afkast_kr"] for r in medlemmer)
        kostpris = v - afkast_kr
        sektor_fordeling.append({"sektor": s, "vaerdi": v, "andel": v / total * 100, "antal": len(medlemmer),
                                 "afkast_pct": afkast_kr / kostpris * 100 if kostpris else 0,
                                 "positioner": medlemmer})
    return rækker, sektor_fordeling


def byg_data(konto, positioner, handler, strategi, fejl=None):
    med_udfald = afgjorte(handler)
    graense_30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    seneste_30 = [h for h in med_udfald if h["dato"][:10] >= graense_30]
    gevinster = [a for h in med_udfald if er_vinder(h) and (a := afkast_pct(h["udfald"])) is not None]
    tab = [a for h in med_udfald if not er_vinder(h) and (a := afkast_pct(h["udfald"])) is not None]
    snit_gevinst = sum(gevinster) / len(gevinster) if gevinster else 0
    snit_tab = sum(tab) / len(tab) if tab else 0
    datoer, samlet, rullende = beregn_hit_rate_over_tid(handler)
    pos_rækker, sektor_fordeling = beregn_positioner(positioner)

    portefolje = float(konto.portfolio_value) if konto else None
    forrige = float(getattr(konto, "last_equity", 0) or 0) if konto else 0
    dagens = (portefolje - forrige) if konto and forrige else None
    cash = float(konto.cash) if konto else None
    investeret = sum(r["vaerdi"] for r in pos_rækker)

    seneste = []
    for h in reversed(handler[-10:]):
        a = afkast_pct(h["udfald"])
        status = "afventer" if h["udfald"] == "afventer" else ("vinder" if er_vinder(h) else "taber")
        seneste.append({**h, "afkast": a, "status": status, "sektor": sektor_for(h["ticker"])})

    return dict(
        fejl=fejl,
        har_konto=konto is not None,
        portefolje=portefolje, dagens=dagens,
        dagens_pct=(dagens / forrige * 100) if dagens is not None else None,
        cash=cash, investeret=investeret,
        investeret_pct=(investeret / portefolje * 100) if portefolje else 0,
        positioner=pos_rækker, sektor_fordeling=sektor_fordeling,
        total_handler=len(handler), afventer=len(handler) - len(med_udfald),
        positive=sum(er_vinder(h) for h in med_udfald),
        negative=sum(not er_vinder(h) for h in med_udfald),
        hit_rate=hit_rate(med_udfald), hit_rate_30=hit_rate(seneste_30), antal_30=len(seneste_30),
        maal=strategi.get("maal_hit_rate", STANDARD_MAAL),
        snit_gevinst=snit_gevinst, snit_tab=snit_tab,
        rr=(snit_gevinst / abs(snit_tab)) if snit_tab else 0,
        datoer=datoer, hit_samlet=samlet, hit_rullende=rullende,
        sektor_hit=beregn_sektor_hit_rate(handler),
        seneste_handler=seneste,
        strategi=strategi,
        tidspunkt=datetime.now().strftime("%d-%m-%Y kl. %H:%M"),
    )


@app.route("/")
def index():
    fejl = None
    konto, positioner = None, []
    try:
        konto = alpaca_client.get_account()
        positioner = alpaca_client.get_all_positions()
    except Exception as e:
        fejl = f"Kunne ikke hente konto fra Alpaca: {e}"
    handler = laes_json("handler_log.json", [])
    strategi = laes_json("strategi.json", {})
    html = open("dashboard_html.html", encoding="utf-8").read()
    data = byg_data(konto, positioner, handler, strategi, fejl)
    data["traener_dage"] = dage_siden_traening(strategi)
    data["traener_koerer"] = traener_koerer()
    data["marked"], data["marked_fejl"] = maaling_mod_marked()
    return render_template_string(html, **data)


_sidste_maalefejl = {"tid": None, "tekst": None}


def maaling_mod_marked():
    """Agentens rigtige afkast mod S&P 500 og Russell 2000 (genberegnes højst én gang i timen)."""
    fejl = _sidste_maalefejl
    if fejl["tid"] and datetime.now() - fejl["tid"] < timedelta(minutes=10):
        return None, fejl["tekst"]
    try:
        from afkast_maaling import hent_maaling
        return hent_maaling(), None
    except Exception as e:
        fejl["tid"], fejl["tekst"] = datetime.now(), f"Kunne ikke måle afkastet mod markedet: {e}"
        return None, fejl["tekst"]


def dage_siden_traening(strategi):
    """Antal dage siden træner-agenten sidst opdaterede strategi.json (None hvis ukendt)"""
    try:
        sidst = datetime.strptime(strategi.get("opdateret", ""), "%Y-%m-%d %H:%M")
        return (datetime.now() - sidst).days
    except ValueError:
        return None


def traener_koerer():
    return subprocess.run(["pgrep", "-f", "traener_agent.py"], capture_output=True).returncode == 0


@app.route("/koer-traener")
def koer_traener_route():
    # Samme som den ugentlige kørsel: opdatér udfald først, så træneren ser de nyeste resultater
    if not traener_koerer():
        log = open("traener.log", "a")
        subprocess.Popen(
            f'"{sys.executable}" opdater_udfald.py; "{sys.executable}" traener_agent.py',
            shell=True, stdout=log, stderr=log
        )
    return redirect("/?traener=1")


@app.route("/koer-agent")
def koer_agent_route():
    subprocess.Popen(["python3", "aktie_agent.py"])
    return redirect("/?startet=1")


if __name__ == "__main__":
    app.run(debug=False, port=5001, host="0.0.0.0")
