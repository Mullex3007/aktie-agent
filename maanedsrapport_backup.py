
import json
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from email_notifikation import send_email

load_dotenv()

LOG_FIL = "handler_log.json"

def generer_maanedsrapport():
    if not os.path.exists(LOG_FIL):
        print("Ingen handler endnu.")
        return

    with open(LOG_FIL) as f:
        handler = json.load(f)

    # Kun handler fra seneste måned
    nu = datetime.now()
    maaned_start = nu.replace(day=1).strftime("%Y-%m")
    
    # Brug alle handler med udfald til statistik
    med_udfald = [h for h in handler if h["udfald"] != "afventer"]
    denne_maaned = [h for h in handler if h["dato"].startswith(maaned_start)]

    # Statistik
    positive = [h for h in med_udfald if "\u2705" in h["udfald"]]
    negative = [h for h in med_udfald if "\u274c" in h["udfald"]]
    hit_rate = len(positive) / len(med_udfald) * 100 if med_udfald else 0

    # Bedste og dårligste aktier
    afkast = defaultdict(list)
    for h in med_udfald:
        try:
            pct_str = h["udfald"].replace("+", "").replace("%", "").strip()
            for tegn in ["\u2705", "\u274c", " "]:
                pct_str = pct_str.replace(tegn, "")
            afkast[h["ticker"]].append(float(pct_str.strip()))
        except:
            pass

    afkast_liste = [(t, sum(v)/len(v), len(v)) for t, v in afkast.items() if len(v) >= 3]
    afkast_liste.sort(key=lambda x: x[1], reverse=True)

    # Byg rapport
    rapport = f"""
🤖 AKTIE-AGENT MÅNEDLIG RAPPORT
{nu.strftime("%B %Y")}
{"="*40}

📊 OVERORDNET STATISTIK
Handler i alt: {len(handler)}
Handler denne måned: {len(denne_maaned)}
Handler med udfald: {len(med_udfald)}
Positive handler: {len(positive)} ✅
Negative handler: {len(negative)} ❌
Hit rate: {hit_rate:.1f}%

🏆 TOP 5 BEDSTE AKTIER:
"""
    for ticker, snit, antal in afkast_liste[:5]:
        rapport += f"  {ticker}: {snit:+.1f}% snit ({antal} handler)\n"

    rapport += "\n💩 TOP 5 DÅRLIGSTE AKTIER:\n"
    for ticker, snit, antal in afkast_liste[-5:]:
        rapport += f"  {ticker}: {snit:+.1f}% snit ({antal} handler)\n"

    rapport += f"""
📈 DENNE MÅNEDS HANDLER:
"""
    for h in denne_maaned[-20:]:
        rapport += f"  {h['dato']}: {h['anbefaling']} {h['ticker']} @ ${h['pris']} → {h['udfald']}\n"

    rapport += f"""
{"="*40}
Rapporten er genereret automatisk af din aktie-agent.
    """

    print(rapport)
    send_email(f"🤖 Månedlig rapport - {nu.strftime('%B %Y')}", rapport)
    print("Rapport sendt!")

if __name__ == "__main__":
    generer_maanedsrapport()
