# Fælles sektorkort til agent, træner-agent og dashboard
_SEKTORER = {
    "Energi": ["CVX", "XOM", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "OXY", "HAL",
               "BP", "SHEL", "TTE", "SU", "ENPH"],
    "Finans": ["JPM", "BAC", "GS", "MS", "C", "WFC", "BLK", "AXP", "USB", "TFC",
               "BK", "STT", "FITB", "HBAN", "RF", "CFG", "KEY", "CMA", "ZION", "FHN",
               "V", "MA", "PYPL", "SQ", "BRK-B", "HSBC", "BARC", "BCS", "UBS", "UBSG",
               "ING", "LYG", "CS", "DB", "BNP", "SAN", "TD", "RY"],
    "Forsikring": ["PGR", "MET", "PRU", "AFL", "ALL", "CB", "TRV", "HIG", "MMC", "AON",
                   "AIG", "LNC", "UNM", "GL", "FG", "CINF", "RLI", "WRB", "ERIE", "SFG", "MFC"],
    "Tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "TXN", "INTC", "QCOM",
             "CRM", "ADBE", "NOW", "SNOW", "PLTR", "SHOP", "ASML", "SAP", "TSM", "SONY",
             "ERIC", "NOK", "NICE", "BABA", "JD", "PDD", "BIDU", "NFLX", "TSLA"],
    "Sundhed": ["ABT", "PFE", "JNJ", "UNH", "MRK", "ABBV", "TMO", "DHR", "BMY", "AMGN",
                "GILD", "REGN", "VRTX", "BIIB", "ILMN", "IQV", "ZBH", "BAX", "BDX", "EW",
                "NVO", "AZN", "GSK", "NOVN", "ROG", "GMAB", "ZLAB", "ASND", "BNTX", "MRNA", "ELAN", "PHG"],
    "Forbrug": ["DIS", "SBUX", "KO", "PEP", "WMT", "COST", "TGT", "HD", "LOW", "GM", "F",
                "EBAY", "ETSY", "ROST", "TJX", "VFC", "MCD", "NKE", "NSRGY", "UL", "ULVR",
                "BTI", "DEO", "TM", "HMC", "UBER", "LYFT"],
    "Industri": ["CAT", "DE", "HON", "GE", "MMM", "UPS", "FDX", "BA", "LMT", "RTX", "NOC",
                 "GD", "HII", "TXT", "SPR", "EMR", "ETN", "PH", "ROK", "IR", "ABB", "SKF", "RELX"],
}

SEKTOR_MAP = {ticker: sektor for sektor, tickers in _SEKTORER.items() for ticker in tickers}


def sektor_for(ticker):
    return SEKTOR_MAP.get(ticker, "Andre")
