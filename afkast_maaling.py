"""
Måler agentens RIGTIGE afkast og sammenligner det med markedet.

Hit rate siger kun, hvor tit en aktie steg 7 dage efter købet. Det her program
ser på, hvad pengene faktisk gav: de rigtige køb og salg hos Alpaca (inkl.
stop-loss og take-profit), minus handelsomkostninger, og sammenligner med hvad
de SAMME dollars havde givet i S&P 500 (SPY) og Russell 2000 (IWM) i de SAMME
dage.

Kør:  python3 afkast_maaling.py
Dashboardet bruger hent_maaling(), som husker resultatet i en time.
"""
import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

HANDEL_URL = "https://paper-api.alpaca.markets"   # Kun paper. Rigtige penge kræver Mortens ja.
DATA_URL = "https://data.alpaca.markets"

# Alpaca tager ingen kurtage, men man betaler altid lidt i spread/slippage.
# 0,10% pr. køb og 0,10% pr. salg er et forsigtigt skøn. Hæv det, hvis rigtige
# penge koster mere (fx valutaveksling DKK -> USD).
OMKOSTNING_PCT = 0.10

# Målet fra 21. oktober: 80% mod S&P 500, 20% småselskaber mod Russell 2000
BENCHMARKS = {"SPY": "S&P 500", "IWM": "Russell 2000"}
VAEGTE = {"SPY": 0.8, "IWM": 0.2}

CACHE_FIL = "afkast_maaling.json"
CACHE_MINUTTER = 60


# ---------------------------------------------------------------- hentning

def _hent(url, params=None):
    headers = {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", ""),
    }
    for forsoeg in range(3):
        svar = requests.get(url, headers=headers, params=params, timeout=30)
        if svar.status_code == 429:          # for mange kald, vent lidt
            time.sleep(2 * (forsoeg + 1))
            continue
        svar.raise_for_status()
        return svar.json()
    svar.raise_for_status()


def hent_udfyldte_ordrer():
    """Alle ordrer der faktisk er blevet handlet (også stop-loss og take-profit)."""
    ordrer, set_id, efter = [], set(), "2000-01-01T00:00:00Z"
    while True:
        side = _hent(f"{HANDEL_URL}/v2/orders", {
            "status": "closed", "limit": 500, "direction": "asc",
            "nested": "false", "after": efter,
        })
        if not side:
            break
        for o in side:
            if o["id"] not in set_id and float(o.get("filled_qty") or 0) > 0 and o.get("filled_at"):
                set_id.add(o["id"])
                ordrer.append(o)
            # Bracket-ordrer kan have ben gemt under "legs"
            for ben in o.get("legs") or []:
                if ben["id"] not in set_id and float(ben.get("filled_qty") or 0) > 0 and ben.get("filled_at"):
                    set_id.add(ben["id"])
                    ordrer.append(ben)
        if len(side) < 500:
            break
        nyt_efter = side[-1]["submitted_at"]
        if nyt_efter == efter:
            break
        efter = nyt_efter
    ordrer.sort(key=lambda o: o["filled_at"])
    return ordrer


def hent_positioner():
    return {p["symbol"]: float(p["current_price"]) for p in _hent(f"{HANDEL_URL}/v2/positions")}


def hent_kurser(symboler, start):
    """Daglige kurser (inkl. udbytte, så indekset får sit fulde afkast)."""
    kurser = defaultdict(dict)
    for feed in ("iex", "sip"):
        try:
            token = None
            while True:
                params = {"symbols": ",".join(symboler), "timeframe": "1Day", "start": start,
                          "adjustment": "all", "feed": feed, "limit": 10000}
                if token:
                    params["page_token"] = token
                data = _hent(f"{DATA_URL}/v2/stocks/bars", params)
                for sym, bars in (data.get("bars") or {}).items():
                    for b in bars:
                        kurser[sym][b["t"][:10]] = (float(b["o"]), float(b["c"]))
                token = data.get("next_page_token")
                if not token:
                    break
            if all(kurser.get(s) for s in symboler):
                return kurser
        except requests.HTTPError:
            continue
    return kurser


def hent_konto_historik():
    data = _hent(f"{HANDEL_URL}/v2/account/portfolio/history",
                 {"period": "1A", "timeframe": "1D", "pnl_reset": "no_reset"})
    punkter = []
    for ts, eq in zip(data.get("timestamp") or [], data.get("equity") or []):
        if eq:  # spring dage over før kontoen havde penge
            punkter.append((datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"), float(eq)))
    return punkter


# ---------------------------------------------------------------- beregning

def kurs_paa(kurser, dato, felt):
    """Kurs på en dato. Er dagen ikke en handelsdag, bruges seneste lukkekurs før."""
    if dato in kurser:
        return kurser[dato][0 if felt == "open" else 1]
    tidligere = [d for d in kurser if d <= dato]
    return kurser[max(tidligere)][1] if tidligere else None


def byg_handler(ordrer, aktuelle_kurser):
    """Parrer køb og salg (først-ind-først-ud) til hele handler.

    Åbne positioner værdisættes til dagens kurs. Et salg uden noget at sælge
    er et short-salg, som lukkes af et senere køb.
    """
    aabne = defaultdict(deque)   # ticker -> [antal (+ lang / - kort), pris, dato]
    handler = []
    for o in ordrer:
        sym = o["symbol"]
        antal = float(o["filled_qty"]) * (1 if o["side"] == "buy" else -1)
        pris = float(o["filled_avg_price"])
        dato = o["filled_at"][:10]
        kø = aabne[sym]
        while antal and kø and (kø[0][0] > 0) != (antal > 0):
            lot = kø[0]
            luk = min(abs(antal), abs(lot[0]))
            handler.append(_handel(sym, luk, lot[0] > 0, lot[1], lot[2], pris, dato, True))
            lot[0] += luk if lot[0] < 0 else -luk
            antal += luk if antal < 0 else -luk
            if abs(lot[0]) < 1e-9:
                kø.popleft()
        if abs(antal) > 1e-9:
            kø.append([antal, pris, dato])

    i_dag = datetime.now().strftime("%Y-%m-%d")
    for sym, kø in aabne.items():
        if sym not in aktuelle_kurser:
            continue
        for antal, pris, dato in kø:
            handler.append(_handel(sym, abs(antal), antal > 0, pris, dato,
                                   aktuelle_kurser[sym], i_dag, False))
    return handler


def _handel(sym, antal, lang, ind_pris, ind_dato, ud_pris, ud_dato, lukket):
    brutto = (ud_pris / ind_pris - 1) * (1 if lang else -1)
    return {
        "ticker": sym, "antal": antal, "retning": "lang" if lang else "kort",
        "ind_dato": ind_dato, "ind_pris": ind_pris, "ud_dato": ud_dato, "ud_pris": ud_pris,
        "lukket": lukket, "investeret": antal * ind_pris,
        "afkast": brutto - 2 * OMKOSTNING_PCT / 100,
    }


def tilfoej_benchmarks(handler, kurser):
    for h in handler:
        for sym in BENCHMARKS:
            ind = kurs_paa(kurser.get(sym, {}), h["ind_dato"], "open")
            ud = kurs_paa(kurser.get(sym, {}), h["ud_dato"], "close")
            h[sym] = (ud / ind - 1) if ind and ud else None
        if h.get("SPY") is not None and h.get("IWM") is not None:
            h["blandet"] = sum(VAEGTE[s] * h[s] for s in VAEGTE)
        else:
            h["blandet"] = h.get("SPY")


def opsummer(handler):
    med = [h for h in handler if h.get("SPY") is not None]
    if not med:
        return None
    investeret = sum(h["investeret"] for h in med)
    kr = lambda felt: sum(h["investeret"] * h[felt] for h in med if h.get(felt) is not None)
    agent_kr, spy_kr, iwm_kr, bland_kr = kr("afkast"), kr("SPY"), kr("IWM"), kr("blandet")
    slog = sum(h["afkast"] > h["SPY"] for h in med)
    return {
        "antal": len(med),
        "lukkede": sum(h["lukket"] for h in med),
        "aabne": sum(not h["lukket"] for h in med),
        "investeret": investeret,
        "agent_kr": agent_kr, "spy_kr": spy_kr, "iwm_kr": iwm_kr, "blandet_kr": bland_kr,
        "agent_pct": agent_kr / investeret * 100,
        "spy_pct": spy_kr / investeret * 100,
        "iwm_pct": iwm_kr / investeret * 100,
        "blandet_pct": bland_kr / investeret * 100,
        "merafkast_pct": (agent_kr - spy_kr) / investeret * 100,
        "merafkast_blandet_pct": (agent_kr - bland_kr) / investeret * 100,
        "slog_spy_pct": slog / len(med) * 100,
    }


def konto_mod_marked(punkter, kurser):
    """Hele kontoens udvikling mod indeksene, i procent fra første dag."""
    if len(punkter) < 2:
        return None
    start_dato, start_eq = punkter[0]
    serie = {"datoer": [], "konto": []}
    for sym in BENCHMARKS:
        serie[sym] = []
    start_kurs = {s: kurs_paa(kurser.get(s, {}), start_dato, "close") for s in BENCHMARKS}
    for dato, eq in punkter:
        serie["datoer"].append(dato)
        serie["konto"].append(round((eq / start_eq - 1) * 100, 2))
        for s in BENCHMARKS:
            k = kurs_paa(kurser.get(s, {}), dato, "close")
            serie[s].append(round((k / start_kurs[s] - 1) * 100, 2) if k and start_kurs[s] else None)
    return {
        "start_dato": start_dato, "start_vaerdi": start_eq, "slut_vaerdi": punkter[-1][1],
        "konto_pct": serie["konto"][-1],
        "spy_pct": serie["SPY"][-1], "iwm_pct": serie["IWM"][-1],
        "serie": serie,
    }


def beregn_maaling():
    ordrer = hent_udfyldte_ordrer()
    positioner = hent_positioner()
    try:
        konto = hent_konto_historik()
    except requests.RequestException as e:
        print(f"⚠️  Kunne ikke hente kontohistorik: {e}")
        konto = []
    handler = byg_handler(ordrer, positioner)
    alle_datoer = [h["ind_dato"] for h in handler] + [p[0] for p in konto]
    start = (min(alle_datoer) if alle_datoer else datetime.now().strftime("%Y-%m-%d"))
    start = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    kurser = hent_kurser(list(BENCHMARKS), start)
    tilfoej_benchmarks(handler, kurser)

    graense_30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return {
        "beregnet": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "omkostning_pct": OMKOSTNING_PCT,
        "handler": opsummer(handler),
        "lukkede": opsummer([h for h in handler if h["lukket"]]),
        "seneste_30": opsummer([h for h in handler if h["ind_dato"] >= graense_30]),
        "konto": konto_mod_marked(konto, kurser),
        "bedste": sorted(handler, key=lambda h: -h["afkast"])[:5],
        "vaerste": sorted(handler, key=lambda h: h["afkast"])[:5],
    }


def hent_maaling(tving=False):
    """Til dashboardet: genbrug målingen i en time, så siden ikke bliver langsom."""
    if not tving and os.path.exists(CACHE_FIL):
        try:
            with open(CACHE_FIL) as f:
                gemt = json.load(f)
            alder = datetime.now() - datetime.strptime(gemt["beregnet"], "%Y-%m-%d %H:%M")
            if alder < timedelta(minutes=CACHE_MINUTTER):
                return gemt
        except (OSError, ValueError, KeyError):
            pass
    maaling = beregn_maaling()
    with open(CACHE_FIL, "w") as f:
        json.dump(maaling, f, indent=2, ensure_ascii=False)
    return maaling


# ---------------------------------------------------------------- rapport

def _pct(x):
    return "–" if x is None else f"{x:+.2f}%".replace(".", ",")


def _kr(x):
    return f"{x:+,.0f} $".replace(",", ".")


def _tal(x):
    return f"{x:,.0f}".replace(",", ".")


def rapport_tekst(m):
    linjer = ["SLÅR AGENTEN MARKEDET?", "=" * 40,
              f"Målt {m['beregnet']} · omkostning {str(m['omkostning_pct']).replace('.', ',')}% pr. køb og pr. salg", ""]
    h = m.get("handler")
    if h:
        linjer += [
            f"Agentens handler ({h['antal']}: {h['lukkede']} lukkede, {h['aabne']} stadig åbne)",
            f"  Investeret i alt:            {_tal(h['investeret'])} $",
            f"  Agenten tjente:              {_kr(h['agent_kr'])}  ({_pct(h['agent_pct'])})",
            f"  Samme penge i S&P 500:       {_kr(h['spy_kr'])}  ({_pct(h['spy_pct'])})",
            f"  Samme penge i Russell 2000:  {_kr(h['iwm_kr'])}  ({_pct(h['iwm_pct'])})",
            f"  Merafkast mod S&P 500:       {_pct(h['merafkast_pct'])}",
            f"  Merafkast mod 80/20-målet:   {_pct(h['merafkast_blandet_pct'])}",
            f"  Handler der slog S&P 500:    {h['slog_spy_pct']:.0f}%",
            "",
        ]
    s = m.get("seneste_30")
    if s:
        linjer += [f"Køb de seneste 30 dage ({s['antal']}): agent {_pct(s['agent_pct'])}, "
                   f"S&P 500 {_pct(s['spy_pct'])}, merafkast {_pct(s['merafkast_pct'])}", ""]
    k = m.get("konto")
    if k:
        linjer += [
            f"Hele kontoen siden {k['start_dato']}",
            f"  Konto:        {_pct(k['konto_pct'])}  ({_tal(k['start_vaerdi'])} $ -> {_tal(k['slut_vaerdi'])} $)",
            f"  S&P 500:      {_pct(k['spy_pct'])}",
            f"  Russell 2000: {_pct(k['iwm_pct'])}",
            "  (Kontoen tæller også de kontanter, der ikke er investeret.)",
            "",
        ]
    if h:
        dom = "SLÅR" if h["merafkast_pct"] > 0 else "SLÅR IKKE"
        linjer.append(f"Konklusion: Agentens handler {dom} S&P 500 lige nu.")
    return "\n".join(linjer)


if __name__ == "__main__":
    print("Henter handler og kurser fra Alpaca ...\n")
    maaling = hent_maaling(tving=True)
    print(rapport_tekst(maaling))
