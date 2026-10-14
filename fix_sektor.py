with open('dashboard.py', 'r') as f:
    kode = f.read()

# Find og ret SEKTOR_MAP
gammel = '"AMGN": "Sundhed",\n}'
ny = '"AMGN": "Sundhed",\n}\n'

if gammel in kode:
    kode = kode.replace(gammel, ny)
    with open('dashboard.py', 'w') as f:
        f.write(kode)
    print("Fixet!")
else:
    # Tilfoej manglende closing bracket
    kode = kode.replace('"AMGN": "Sundhed",', '"AMGN": "Sundhed"\n}')
    with open('dashboard.py', 'w') as f:
        f.write(kode)
    print("Fixet!")