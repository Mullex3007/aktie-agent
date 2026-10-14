with open('screening.py', 'r') as f:
    kode = f.read()

kode = kode.replace(
    '    # Nordisk via US listing\n    "ERIC", "NOK", "NICE", "WPM", "MFC", "SU", "TD", "RY",',
    '    # Nordisk via US listing\n    "ERIC", "NOK", "SKF", "NICE", "WPM", "MFC", "SU", "TD", "RY",\n    # Danske selskaber med US listing\n    "NVO", "GMAB", "ZLAB", "ASND", "BNTX", "COLO",\n    "NNDM", "AMBU", "COPEN", "BAVARIAN",'
)

with open('screening.py', 'w') as f:
    f.write(kode)
print("Nordiske og danske aktier tilføjet!")
