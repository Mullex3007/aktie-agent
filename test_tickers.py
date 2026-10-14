import finnhub
import os
from dotenv import load_dotenv
load_dotenv()

client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))

test = [
    "GMAB", "NVO", "NNDM", "ZLAB", "ASND",
    "BNTX", "ERIC", "NOK", "VOLV", "SAND",
    "SKF", "ATCO", "ALFA", "HEXAB", "SINCH",
    "LUNE", "COLO", "PNDORA", "VESTAS", "ORSTED"
]

for ticker in test:
    try:
        quote = client.quote(ticker)
        pris = quote.get("c", 0)
        if pris > 0:
            print(f"OK {ticker}: {pris}")
        else:
            print(f"NEJ {ticker}: ingen data")
    except:
        print(f"FEJL {ticker}")
