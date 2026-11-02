import json
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from email_notifikation import send_email

load_dotenv()

LOG_FIL = "handler_log.json"

KRITERIER = """
HANDELSSTRATEGIENS KRITERIER
==============================
Agenten handler ud fra følgende kriterier:

1. SCREENING (213 aktier analyseres dagligt):
   - P/E ratio under 25 (aktien er billig ift. indtjening)
   - Inden for 40% af 52-ugers lav (aktien er faldet meget)

2. AI-ANALYSE (Claude vurderer screenede aktier):
   - Kun KØB-anbefalinger med konfidensgrad over 70%
   - Claude vurderer P/E, P/B, 52-ugers interval og historik
   - Tidligere handler indgår i vurderingen

3. FOKUSSEKTORER (baseret på mønsteranalyse):
   - Forsikring og finans (historisk 79-85% success)
   - Energi (historisk 59-100% success)
   - Selektiv tech og sundhed

4. SIKKERHED:
   - Maksimalt 1 handel per aktie per dag
   - Kun paper trading indtil hit rate overstiger 60%
==============================
"""

def generer_maanedsrapport():
    if not os.path.exists(LOG_FIL):
        print("Ingen handler endnu.")
        return

    with open(LOG_FIL) as f:
        handler = json.load(f)

    nu = datetime.now()
    denne_maaned = nu.strftime("%Y-%m")

    alle_med_udfald = [h for h in handler if h["udfald"] != "afventer"]
    maaneds_handler = [h for h in handler if h["dato"].startswith(denne_maaned)]

    positive = len([h for h in alle_med_udfald if "\u2705" in h["udfald"]])
    negative = len([h for h in alle_med_udfald if "\u274c" in h["udfald"]])
    hit_rate = round(positive / len(alle_med_udfald) * 100, 1) if alle_med_udfald else 0

    afkast = defaultdict(list)
    for h in alle_med_udfald:
        try:
            pct_str = h["udfald"].replace("+", "").replace("%", "").strip()
            for tegn in ["\u2705", "\u274c", " "]:
                pct_str = pct_str.replace(tegn, "")
            afkast[h["ticker"]].append(float(pct_str.strip()))
        except:
            pass

    afkast_liste = [(t, sum(v)/len(v), len(v)) for t, v in afkast.items() if len(v) >= 3]
    afkast_liste.sort(key=lambda x: x[1], reverse=True)

    rapport = "AKTIE-AGENT MAANEDLIG RAPPORT\n"
    rapport += nu.strftime("%B %Y") + "\n"
    rapport += "="*40 + "\n\n"
    rapport += KRITERIER + "\n"
    rapport += "OVERORDNET STATISTIK\n"
    rapport += "-"*40 + "\n"
    rapport += f"Handler i alt: {len(handler)}\n"
    rapport += f"Handler denne maaned: {len(maaneds_handler)}\n"
    rapport += f"Handler med udfald: {len(alle_med_udfald)}\n"
    rapport += f"Positive handler: {positive}\n"
    rapport += f"Negative handler: {negative}\n"
    rapport += f"Hit rate: {hit_rate}%\n\n"

    rapport += "TOP 5 BEDSTE AKTIER:\n"
    for ticker, snit, antal in afkast_liste[:5]:
        rapport += f"  {ticker}: {snit:+.1f}% snit ({antal} handler)\n"

    rapport += "\nTOP 5 DAARLIGSTE AKTIER:\n"
    for ticker, snit, antal in afkast_liste[-5:]:
        rapport += f"  {ticker}: {snit:+.1f}% snit ({antal} handler)\n"

    rapport += f"\nDENNE MAANEDS HANDLER ({len(maaneds_handler)} i alt):\n"
    rapport += "-"*40 + "\n"

    for h in maaneds_handler:
        rapport += f"\n  {h['dato']}: {h['anbefaling']} {h['ticker']} @ ${h['pris']}\n"
        if h.get('begrundelse'):
            rapport += f"  Begrundelse: {h['begrundelse']}\n"
        rapport += f"  Udfald: {h['udfald']}\n"

    try:
        from afkast_maaling import hent_maaling, rapport_tekst
        rapport += "\n\n" + rapport_tekst(hent_maaling(tving=True)) + "\n"
    except Exception as e:
        rapport += f"\n\nKunne ikke måle afkastet mod markedet: {e}\n"

    rapport += "\n" + "="*40 + "\n"
    rapport += "Rapporten er genereret automatisk af din aktie-agent.\n"

    print(rapport)
    send_email("Aktie-Agent Maanedlig Rapport " + nu.strftime("%B %Y"), rapport)
    print("Rapport sendt!")

if __name__ == "__main__":
    generer_maanedsrapport()