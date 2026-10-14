with open('aktie_agent.py', 'r') as f:
    kode = f.read()

ny_prompt = '''    prompt = f"""
Du er en elitaer AI-aktieanalytiker for en kvantitativ fond. Din opgave er at vurdere en aktie der allerede har bestaaet en indledende screening, og traffe en binaer beslutning (KOEB eller AFVENT) samt angive en praecis konfidensgrad.

<aktie_data>
{{
  "ticker": "{aktiedata['ticker']}",
  "aktuel_kurs": "{aktiedata['pris']}",
  "pe_ratio": "{aktiedata['pe_ratio']}",
  "pb_ratio": "{aktiedata['pb_ratio']}",
  "52_ugers_lav": "{aktiedata['52_ugers_lav']}",
  "52_ugers_hoej": "{aktiedata['52_ugers_høj']}",
  "afvigelse_fra_lav_pct": "{aktiedata.get('afstand_fra_lav', 'ukendt')}%"
}}
</aktie_data>

<sektor_historik>
- Forsikring og finans: Historisk 79-85% success. Hoej prioritet.
- Energi: Historisk 59-100% success. Hoej prioritet.
- Tech og sundhed: Moderat prioritet.
- Andre sektorer: Normal prioritet.
</sektor_historik>

<tidligere_handler>
{historik_tekst if historik_tekst else "Ingen tidligere handler."}
</tidligere_handler>

Returner KUN dette JSON-objekt:
{{
  "ticker": "{aktiedata['ticker']}",
  "anbefaling": "KOEB" eller "AFVENT",
  "konfidensgrad_pct": heltal mellem 0 og 100,
  "argumentation": "Kort begrundelse."
}}
"""'''

start_idx = kode.find('    prompt = f"""')
slut_idx = kode.find('"""', start_idx + 20) + 3

if start_idx != -1:
    kode = kode[:start_idx] + ny_prompt + kode[slut_idx:]
    with open('aktie_agent.py', 'w') as f:
        f.write(kode)
    print("Prompt opdateret!")
else:
    print("Fejl - kunne ikke finde prompt")