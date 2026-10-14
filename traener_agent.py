import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
LOG_FIL = "handler_log.json"
STRATEGI_FIL = "strategi.json"

def analyser_mønstre():
    with open(LOG_FIL) as f:
        handler = json.load(f)

    med_udfald = [h for h in handler if h["udfald"] != "afventer"]

    ticker_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "afkast": []})
    sektor_stats = defaultdict(lambda: {"wins": 0, "losses": 0})

    SEKTOR_MAP = {
        "JPM": "Finans", "BAC": "Finans", "GS": "Finans", "MS": "Finans",
        "C": "Finans", "WFC": "Finans", "AXP": "Finans", "USB": "Finans",
        "TFC": "Finans", "PGR": "Forsikring", "PRU": "Forsikring",
        "AFL": "Forsikring", "ALL": "Forsikring", "CB": "Forsikring",
        "HIG": "Forsikring", "AON": "Forsikring", "CVX": "Energi",
        "XOM": "Energi", "BP": "Energi", "SHEL": "Energi",
        "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "AMZN": "Tech",
        "META": "Tech", "NVDA": "Tech", "ABT": "Sundhed", "PFE": "Sundhed",
        "NVO": "Sundhed", "GMAB": "Sundhed"
    }

    for h in med_udfald:
        ticker = h["ticker"]
        try:
            pct_str = h["udfald"].replace("+", "").replace("%", "").strip()
            for tegn in ["\u2705", "\u274c", " "]:
                pct_str = pct_str.replace(tegn, "")
            pct = float(pct_str.strip())
            if "\u2705" in h["udfald"]:
                ticker_stats[ticker]["wins"] += 1
                sektor_stats[SEKTOR_MAP.get(ticker, "Andre")]["wins"] += 1
            else:
                ticker_stats[ticker]["losses"] += 1
                sektor_stats[SEKTOR_MAP.get(ticker, "Andre")]["losses"] += 1
            ticker_stats[ticker]["afkast"].append(pct)
        except:
            pass

    statistik = "HANDELSSTATISTIK:\n\n"
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

    return statistik

def kør_traeningsagent():
    print("Traener-agent starter...\n")

    statistik = analyser_mønstre()
    print(statistik)

    prompt = f"""
Du er en erfaren kvantitativ porteføljemanager med 20 aars erfaring fra en top-tier hedgefond.
Din specialitet er at analysere algoritmiske handelsstrategiers performance og optimere dem
baseret paa historiske data.

Din opgave er at gennemgaa nedenstaaende handelsdata med et kritisk og analytisk blik -
som en "post-mortem" analyse - og identificere praecist hvad der skal justeres for at
lofte hit raten fra 46% mod 70%+.

Du er DATA-DREVET og lader aldrig mavefornemmelser styre dine konklusioner.
Du fokuserer paa statistisk signifikante mønstre og ignorerer støj.

<handelsdata>
{statistik}
</handelsdata>

<nuvaerende_strategi>
- P/E under 25
- Inden for 40% af 52-ugers lav
- Fokus paa finans, forsikring og energi
- Konfidensgraense: 75%
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
    "justeret_konfidensgraense": tal mellem 70 og 90
}}
"""

    besked = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    tekst = besked.content[0].text
    tekst = tekst.strip().replace("```json", "").replace("```", "").strip()

    try:
        laering = json.loads(tekst)
        laering["opdateret"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(STRATEGI_FIL, "w") as f:
            json.dump(laering, f, indent=2, ensure_ascii=False)

        print("\nTRAENER-AGENT KONKLUSIONER:")
        print(f"Analyse: {laering.get('analyse', '')}")
        print(f"\nAnbefalinger:")
        for a in laering.get("anbefalinger", []):
            print(f"  - {a}")
        print(f"\nUndgaa aktier: {laering.get('undgaa_aktier', [])}")
        print(f"Fokus aktier: {laering.get('fokus_aktier', [])}")
        print(f"Justeret max P/E: {laering.get('justeret_max_pe', 25)}")
        print(f"Justeret afstand fra lav: {laering.get('justeret_max_afstand_fra_lav', 0.4)}")
        print(f"Justeret konfidensgraense: {laering.get('justeret_konfidensgraense', 75)}%")
        print(f"\nStrategi gemt i {STRATEGI_FIL}")

    except Exception as e:
        print(f"Fejl ved parsing: {e}")
        print(tekst)

if __name__ == "__main__":
    kør_traeningsagent()