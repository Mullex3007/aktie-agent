import json
import os

STRATEGI_FIL = "strategi.json"

# Bruges hvis strategi.json mangler eller en værdi er ugyldig
STANDARD = {
    "justeret_max_pe": 18,
    "justeret_max_afstand_fra_lav": 0.25,
    "justeret_konfidensgraense": 78,
    "stop_loss_pct": 5,
    "take_profit_pct": 8,
    "maal_hit_rate": 60,
    "undgaa_aktier": [],
    "fokus_aktier": [],
    "fokus_sektorer": [],
    "analyse": "",
}

# Træner-agenten kan kun flytte tallene inden for disse grænser
GRAENSER = {
    "justeret_max_pe": (10, 25),
    "justeret_max_afstand_fra_lav": (0.1, 0.5),
    "justeret_konfidensgraense": (55, 90),
    "stop_loss_pct": (2, 15),
    "take_profit_pct": (3, 30),
    "maal_hit_rate": (50, 90),
}


def hent_strategi():
    """Læser strategi.json fra træner-agenten og holder tallene inden for grænserne"""
    strategi = dict(STANDARD)
    if os.path.exists(STRATEGI_FIL):
        try:
            with open(STRATEGI_FIL) as f:
                data = json.load(f)
            strategi.update({k: v for k, v in data.items() if v is not None})
        except Exception as e:
            print(f"⚠️  Kunne ikke læse {STRATEGI_FIL}, bruger standard: {e}")

    for nøgle, (lav, høj) in GRAENSER.items():
        try:
            strategi[nøgle] = min(max(float(strategi[nøgle]), lav), høj)
        except (TypeError, ValueError):
            strategi[nøgle] = STANDARD[nøgle]

    for nøgle in ["undgaa_aktier", "fokus_aktier", "fokus_sektorer"]:
        værdi = strategi.get(nøgle) or []
        strategi[nøgle] = [str(v).strip() for v in værdi if str(v).strip()]
    strategi["undgaa_aktier"] = [t.upper() for t in strategi["undgaa_aktier"]]
    strategi["fokus_aktier"] = [t.upper() for t in strategi["fokus_aktier"]]
    return strategi


def gem_strategi(strategi):
    with open(STRATEGI_FIL, "w") as f:
        json.dump(strategi, f, indent=2, ensure_ascii=False)


def claude_tekst(besked):
    """Henter svaret fra Claude. Nyere modeller sender en tænke-blok først, så vi tager kun tekst-blokkene."""
    if besked.stop_reason == "refusal":
        raise ValueError("Claude afviste forespørgslen")
    tekst = "".join(b.text for b in besked.content if b.type == "text")
    if not tekst:
        raise ValueError(f"Intet tekstsvar fra Claude (stop: {besked.stop_reason})")
    return tekst
