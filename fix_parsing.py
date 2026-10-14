with open('aktie_agent.py', 'r') as f:
    kode = f.read()

kode = kode.replace(
    'tekst = tekst.strip().replace("```json", "").replace("```", "").strip()\n    return json.loads(tekst)',
    '''tekst = tekst.strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(tekst)
    if "konfidensgrad_pct" in data:
        return {
            "anbefaling": "KØB" if data.get("anbefaling") == "KOEB" else "HOLD",
            "begrundelse": data.get("argumentation", ""),
            "konfidensgrad": data.get("konfidensgrad_pct", 0)
        }
    return data'''
)

with open('aktie_agent.py', 'w') as f:
    f.write(kode)
print("Parsing fixet!")
