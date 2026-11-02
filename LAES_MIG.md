# Opdatering 14. oktober 2026

Læg filerne i din aktie-agent-mappe og overskriv de gamle. Din .env og handler_log.json røres ikke.

## Nyt
- strategi.py: læser strategi.json og holder træner-agentens tal inden for faste grænser.
- sektorer.py: ét fælles sektorkort til agent, træner-agent og dashboard.
- beskyt_positioner.py: giver dine åbne positioner stop-loss og take-profit. Kør den én gang nu.

## Ændret
- aktie_agent.py: hvert køb er en bracket-ordre med stop-loss og take-profit. Grænser og blackliste kommer fra strategi.json. Ingen dobbelthandler. Et dårligt svar fra Claude springes over i stedet for at stoppe kørslen.
- screening.py: bruger strategi.json, fjerner dubletter og ugyldige tickers og springer over aktier med forkerte kursdata.
- traener_agent.py: ser den rigtige hit rate (samlet og 30 dage) og dit mål, justerer også stop-loss og take-profit og logger hver kørsel i strategi_historik.json.
- dashboard.py: bruger det fælles sektorkort.
- strategi.json: har fået stop_loss_pct (5), take_profit_pct (8) og maal_hit_rate (60).

## Kør
    python3 beskyt_positioner.py   # én gang nu
    python3 aktie_agent.py         # dagligt
    python3 opdater_udfald.py      # dagligt
    python3 traener_agent.py       # ugentligt

Modellen er nu claude-sonnet-5-5. Du kan ændre den med CLAUDE_MODEL i .env.

# Opdatering 2. november 2026: Slår agenten markedet? (v6)

- afkast_maaling.py (ny): henter de rigtige køb og salg fra Alpaca (også stop-loss og take-profit), trækker 0,10% fra pr. køb og pr. salg, og sammenligner med hvad de samme dollars havde givet i S&P 500 (SPY) og Russell 2000 (IWM) i de samme dage. Viser også hele kontoen mod indeksene. Kør: `python3 afkast_maaling.py`
- dashboard.py og dashboard_html.html: ny boks øverst, "Slår agenten markedet?", med graf. Målingen genberegnes højst én gang i timen.
- maanedsrapport.py: månedsrapporten får målingen med.
