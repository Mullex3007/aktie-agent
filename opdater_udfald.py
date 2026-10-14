import os
import json
import finnhub
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))
LOG_FIL = "handler_log.json"

def opdater_udfald():
    if not os.path.exists(LOG_FIL):
        print("Ingen handler endnu.")
        return

    with open(LOG_FIL, "r") as f:
        handler = json.load(f)

    opdateret = 0
    for handel in handler:
        if handel.get("udfald") != "afventer":
            continue

        # Tjek om der er gået mindst 7 dage
        handel_dato = datetime.strptime(handel["dato"], "%Y-%m-%d %H:%M")
        if datetime.now() < handel_dato + timedelta(days=7):
            continue

        # Hent nuværende pris
        try:
            quote = finnhub_client.quote(handel["ticker"])
            nuværende_pris = quote.get("c", 0)
            indkøbspris = float(handel["pris"])

            if indkøbspris > 0:
                ændring = ((nuværende_pris - indkøbspris) / indkøbspris) * 100
                if handel["anbefaling"] == "SÆLG":
                    ændring = -ændring

                if ændring >= 0:
                    handel["udfald"] = f"✅ +{ændring:.1f}%"
                else:
                    handel["udfald"] = f"❌ {ændring:.1f}%"

                opdateret += 1
                print(f"Opdateret {handel['ticker']}: {handel['udfald']}")
        except Exception as e:
            print(f"Fejl ved {handel['ticker']}: {e}")

    with open(LOG_FIL, "w") as f:
        json.dump(handler, f, indent=2)

    print(f"\n✅ {opdateret} handler opdateret.")

if __name__ == "__main__":
    opdater_udfald()
