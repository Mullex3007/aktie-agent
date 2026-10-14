with open('aktie_agent.py', 'r') as f:
    kode = f.read()

kode = kode.replace(
    'data = json.loads(tekst)\n    return data',
    '''data = json.loads(tekst)
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
print("Parsing opdateret!")
