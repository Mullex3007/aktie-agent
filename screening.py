
import finnhub
import os
from dotenv import load_dotenv

load_dotenv()

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))

# 200 aktier fordelt på regioner og sektorer
ALLE_AKTIER = [
    # US Energi
    "CVX", "XOM", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "OXY", "HAL",
    # US Finans
    "JPM", "BAC", "GS", "C", "WFC", "BLK", "AXP", "USB", "TFC",
    "PGR", "MET", "PRU", "AFL", "ALL", "CB", "TRV", "HIG", "MMC", "AON",
    # US Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "TXN", "INTC",
    "CRM", "ADBE", "NOW", "SNOW", "PLTR", "UBER", "LYFT", "SHOP", "SQ",
    # US Sundhed
    "ABT", "PFE", "JNJ", "UNH", "MRK", "ABBV", "TMO", "DHR", "BMY", "AMGN",
    "GILD", "REGN", "VRTX", "BIIB", "ILMN", "IQV", "ZBH", "BAX", "BDX", "EW",
    # US Forbrug
    "DIS", "SBUX", "KO", "WMT", "COST", "TGT", "HD",
    "LOW", "AMZN", "GM", "F", "EBAY", "ETSY", "ROST", "TJX", "VFC",
    # US Industri
    "CAT", "DE", "HON", "GE", "MMM", "UPS", "FDX", "BA", "LMT", "RTX",
    "NOC", "GD", "HII", "TXT", "SPR", "EMR", "ETN", "PH", "ROK", "IR",
    # Europa
    "ASML", "SAP", "NVO", "SHEL", "BP", "TTE", "NOVN", "ROG", "UBSG",
    "AZN", "GSK", "ULVR", "RIO", "GLEN", "BHP", "VOD", "BT", "HSBC", "BARC",
    # Asien/Global
    "TM", "SONY", "BABA", "JD", "PDD", "BIDU", "TSM", "Samsung", "HMC", "NTT",
    # Europa (US-listede)
    "NVO", "ASML", "SAP", "SHEL", "BP", "AZN", "GSK", "HSBC",
    "UL", "RDS-A", "BTI", "DEO", "BCS", "ING", "ABB", "ELAN",
    "RELX", "PHG", "LYG", "CS", "UBS", "DB", "BNP", "SAN",
    # Nordisk via US listing
    "ERIC", "NOK", "SKF", "NICE", "WPM", "MFC", "SU", "TD", "RY",
    # Danske selskaber med US listing
    "NVO", "GMAB", "ZLAB", "ASND", "BNTX", "COLO",
    "NNDM", "AMBU", "COPEN", "BAVARIAN",
    # Forsikring (stærk sektor!)
    "PGR", "PRU", "AFL", "ALL", "CB", "HIG", "AON", "MMC", "TRV", "AIG",
    "MET", "LNC", "UNM", "GL", "FG", "CINF", "RLI", "WRB", "ERIE", "SFG",
    # Flere finans
    "BK", "STT", "FITB", "HBAN", "RF", "CFG", "KEY", "CMA", "ZION", "FHN",
]

def screen_aktier(max_pe=18, max_pb=999, pct_fra_lav=0.25):
    """Screener aktier baseret på nøgletal - ingen AI bruges her"""
    print(f"🔍 Screener {len(ALLE_AKTIER)} aktier...")
    print(f"   Kriterier: P/E < {max_pe}, P/B < {max_pb}, inden for {pct_fra_lav*100:.0f}% af 52-ugers lav")
    print()
    
    kvalificerede = []
    
    for ticker in ALLE_AKTIER:
        try:
            quote = finnhub_client.quote(ticker)
            metrics = finnhub_client.company_basic_financials(ticker, "all")
            m = metrics.get("metric", {})
            
            pris = quote.get("c", 0)
            pe = m.get("peTTM", None)
            pb = m.get("pbQuarterly", None)
            lav_52 = m.get("52WeekLow", 0)
            høj_52 = m.get("52WeekHigh", 0)
            
            if not pris or not pe or not pb or not lav_52:
                continue
            
            # Beregn hvor tæt på 52-ugers lav
            afstand_fra_lav = (pris - lav_52) / lav_52 if lav_52 > 0 else 999
            
            # Tjek alle kriterier
            if pe < max_pe and pb < max_pb and afstand_fra_lav <= pct_fra_lav:
                kvalificerede.append({
                    "ticker": ticker,
                    "pris": pris,
                    "pe_ratio": round(pe, 2),
                    "pb_ratio": round(pb, 2),
                    "52_ugers_høj": høj_52,
                    "52_ugers_lav": lav_52,
                    "afstand_fra_lav": round(afstand_fra_lav * 100, 1),
                    "navn": ticker
                })
                print(f"✅ {ticker}: P/E={pe:.1f}, P/B={pb:.2f}, {afstand_fra_lav*100:.1f}% fra lav")
        except Exception as e:
            pass
    
    print(f"\n📊 {len(kvalificerede)} aktier klarede screeningen ud af {len(ALLE_AKTIER)}")
    return kvalificerede

if __name__ == "__main__":
    resultat = screen_aktier()
    print("\nKvalificerede aktier:")
    for a in resultat:
        print(f"  {a['ticker']}")
