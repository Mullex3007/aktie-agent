import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta
from strategi import hent_strategi, gem_strategi, GRAENSER, claude_tekst
from sektorer import sektor_for

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
LOG_FIL = "handler_log.json"
HISTORIK_FIL = "strategi_historik.json"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

def analyser_mønstre():
    with open(LOG_FIL) as f:
        handler = json.load(f)

    med_udfald = [h for h in handler if h["udfald"] != "afventer"]

    ticker_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "afkast": []})
    sektor_stats = defaultdict(lambda: {"wins": 0, "losses": 0})


    for h in med_udfald:
        ticker = h["ticker"]
        try:
            pct_str = h["udfald"].replace("+", "").replace("%", "").strip()
            for tegn in ["\u2705", "\u274c", " "]:
                pct_str = pct_str.replace(tegn, "")
            pct = float(pct_str.strip())
            if "\u2705" in h["udfald"]:
                ticker_stats[ticker]["wins"] += 1
                sektor_stats[sektor_for(ticker)]["wins"] += 1
            else:
                ticker_stats[ticker]["losses"] += 1
                sektor_stats[sektor_for(ticker)]["losses"] += 1
            ticker_stats[ticker]["afkast"].append(pct)
        except:
            pass

    # Samlet og seneste 30 dages hit rate, så træneren kan se om det går fremad
    def hit_rate(liste):
        vundne = len([h for h in liste if "\u2705" in h["udfald"]])
        return round(vundne / len(liste) * 100, 1) if liste else 0
    graense = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    seneste = [h for h in med_udfald if h["dato"] >= graense]
    nøgletal = {
        "hit_rate": hit_rate(med_udfald),
        "hit_rate_30_dage": hit_rate(seneste),
        "handler_med_udfald": len(med_udfald),
        "handler_30_dage": len(seneste),
    }

    statistik = "HANDELSSTATISTIK:\n\n"
    statistik += f"Samlet hit rate: {nøgletal['hit_rate']}% ({len(med_udfald)} handler)\n"
    statistik += f"Hit rate seneste 30 dage: {nøgletal['hit_rate_30_dage']}% ({len(seneste)} handler)\n\n"
    statistik += "SEKTOR PERFORMANCE:\n"
    for sektor, stats in sorted(sektor_stats.items()):
        total = stats["wins"] + stats["losses"]
        if total > 0:
            hit_rate = stats["wins"] / total * 100
            statistik += f"  {sektor}: {hit_rate:.0f}% hit rate ({total} handler)\n"

    statistik += "\nBEDSTE AKTIER (min 3 handler):\n"
    resultater = []
    for ticker, stats in ticker_stats.items():
        total = stats["wins"] + stats["losses"]
        if total >= 3:
            hit_rate = stats["wins"] / total * 100
            snit = sum(stats["afkast"]) / len(stats["afkast"])
            resultater.append((ticker, hit_rate, snit, total))
    resultater.sort(key=lambda x: x[1], reverse=True)
    for ticker, hit_rate, snit, total in resultater[:10]:
        statistik += f"  {ticker}: {hit_rate:.0f}% hit rate, {snit:+.1f}% snit ({total} handler)\n"

    statistik += "\nDAARLIGSTE AKTIER (min 3 handler):\n"
    for ticker, hit_rate, snit, total in resultater[-10:]:
        statistik += f"  {ticker}: {hit_rate:.0f}% hit rate, {snit:+.1f}% snit ({total} handler)\n"

    med_begrundelse = [h for h in med_udfald if h.get("begrundelse")][-20:]
    statistik += "\nSENESTE BEGRUNDELSER OG UDFALD:\n"
    for h in med_begrundelse:
        statistik += f"  {h['ticker']} {h['anbefaling']}: {h.get('begrundelse', '')[:100]} -> {h['udfald']}\n"

    return statistik, nøgletal

def gem_historik(nøgletal, strategi):
    historik = []
    if os.path.exists(HISTORIK_FIL):
        with open(HISTORIK_FIL) as f:
            historik = json.load(f)
    historik.append({
        "dato": datetime.now().strftime("%Y-%m-%d %H:%M"),
        **nøgletal,
        **{k: strategi[k] for k in GRAENSER},
    })
    with open(HISTORIK_FIL, "w") as f:
        json.dump(historik, f, indent=2, ensure_ascii=False)

def kør_traeningsagent():
    print("Traener-agent starter...\n")

    statistik, nøgletal = analyser_mønstre()
    print(statistik)
    nu = hent_strategi()
    maal = nu["maal_hit_rate"]

    prompt = f"""
Du er en erfaren kvantitativ porteføljemanager med 20 aars erfaring fra en top-tier hedgefond.
Din specialitet er at analysere algoritmiske handelsstrategiers performance og optimere dem
baseret paa historiske data.

Din opgave er at gennemgaa nedenstaaende handelsdata med et kritisk og analytisk blik -
som en "post-mortem" analyse - og identificere praecist hvad der skal justeres for at
lofte hit raten fra {nøgletal['hit_rate_30_dage']}% (seneste 30 dage) til maalet paa {maal:.0f}%.
Alle handler faar automatisk stop-loss og take-profit, saa du skal ogsaa justere dem.

Du er DATA-DREVET og lader aldrig mavefornemmelser styre dine konklusioner.
Du fokuserer paa statistisk signifikante mønstre og ignorerer støj.

<handelsdata>
{statistik}
</handelsdata>

<nuvaerende_strategi>
- P/E under {nu['justeret_max_pe']:.0f}
- Inden for {nu['justeret_max_afstand_fra_lav'] * 100:.0f}% af 52-ugers lav
- Konfidensgraense: {nu['justeret_konfidensgraense']:.0f}%
- Stop-loss: {nu['stop_loss_pct']}% under koebspris
- Take-profit: {nu['take_profit_pct']}% over koebspris
- Fokussektorer: {", ".join(nu['fokus_sektorer']) or "ingen"}
- Aktier der undgaas: {", ".join(nu['undgaa_aktier']) or "ingen"}
</nuvaerende_strategi>

Udfør en grundig post-mortem analyse og returner KUN dette JSON-objekt:
{{
    "analyse": "præcis datadriven analyse af hvad der virker og ikke virker",
    "anbefalinger": ["konkret anbefaling 1", "konkret anbefaling 2", "konkret anbefaling 3"],
    "undgaa_aktier": ["aktier der konsekvent taber"],
    "fokus_aktier": ["aktier der konsekvent vinder"],
    "justeret_max_pe": tal mellem 10 og 25,
    "justeret_max_afstand_fra_lav": tal mellem 0.2 og 0.5,
    "fokus_sektorer": ["sektorer at prioritere baseret paa data"],
    "justeret_konfidensgraense": tal mellem 55 og 90,
    "stop_loss_pct": tal mellem 2 og 15,
    "take_profit_pct": tal mellem 3 og 30
}}
"""

    besked = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        tekst = claude_tekst(besked)
    except ValueError as e:
        print(f"Fejl fra Claude - strategi.json er IKKE aendret: {e}")
        return
    start, slut = tekst.find("{"), tekst.rfind("}")

    try:
        laering = json.loads(tekst[start:slut + 1])
        # Målet sætter du selv - træneren må ikke ændre det
        laering["maal_hit_rate"] = maal
        laering["opdateret"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        gem_strategi(laering)
        ny = hent_strategi()  # holder tallene inden for grænserne
        gem_strategi({**laering, **{k: ny[k] for k in GRAENSER}})
        gem_historik(nøgletal, ny)

        print("\nTRAENER-AGENT KONKLUSIONER:")
        print(f"Analyse: {laering.get('analyse', '')}")
        print(f"\nAnbefalinger:")
        for a in laering.get("anbefalinger", []):
            print(f"  - {a}")
        print(f"\nUndgaa aktier: {laering.get('undgaa_aktier', [])}")
        print(f"Fokus aktier: {laering.get('fokus_aktier', [])}")
        print(f"Justeret max P/E: {ny['justeret_max_pe']}")
        print(f"Justeret afstand fra lav: {ny['justeret_max_afstand_fra_lav']}")
        print(f"Justeret konfidensgraense: {ny['justeret_konfidensgraense']}%")
        print(f"Stop-loss: {ny['stop_loss_pct']}%, take-profit: {ny['take_profit_pct']}%")
        print(f"Hit rate: {nøgletal['hit_rate_30_dage']}% seneste 30 dage, maal {maal:.0f}%")
        print(f"\nStrategi gemt i strategi.json - agenten bruger den ved naeste koersel")

    except Exception as e:
        print(f"Fejl ved parsing - strategi.json er IKKE aendret: {e}")
        print(tekst)

if __name__ == "__main__":
    kør_traeningsagent()