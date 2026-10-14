
import json
from collections import defaultdict

with open('handler_log.json') as f:
    handler = json.load(f)

data = [h for h in handler if h['udfald'] != 'afventer']

aktie_stats = defaultdict(lambda: {'positive': 0, 'negative': 0, 'total': 0})

for h in data:
    ticker = h['ticker']
    aktie_stats[ticker]['total'] += 1
    if chr(9989) in h['udfald']:
        aktie_stats[ticker]['positive'] += 1
    else:
        aktie_stats[ticker]['negative'] += 1

anbefaling_stats = defaultdict(lambda: {'positive': 0, 'negative': 0})
for h in data:
    a = h['anbefaling']
    if chr(9989) in h['udfald']:
        anbefaling_stats[a]['positive'] += 1
    else:
        anbefaling_stats[a]['negative'] += 1

print("=" * 50)
print("MONSTERANALYSE")
print("=" * 50)

print("\nBEDSTE AKTIER (min. 3 handler):")
resultater = []
for ticker, stats in aktie_stats.items():
    if stats['total'] >= 3:
        hit_rate = stats['positive'] / stats['total'] * 100
        resultater.append((ticker, hit_rate, stats['total']))
resultater.sort(key=lambda x: x[1], reverse=True)
for ticker, hit_rate, total in resultater[:10]:
    print(f"  {ticker}: {hit_rate:.0f}% success ({total} handler)")

print("\nDAARLIGSTE AKTIER (min. 3 handler):")
for ticker, hit_rate, total in resultater[-10:]:
    print(f"  {ticker}: {hit_rate:.0f}% success ({total} handler)")

print("\nKOEB vs SAELG:")
for anbefaling, stats in anbefaling_stats.items():
    total = stats['positive'] + stats['negative']
    hit_rate = stats['positive'] / total * 100
    print(f"  {anbefaling}: {hit_rate:.0f}% success ({total} handler)")

afkast = defaultdict(list)
for h in data:
    if h['udfald'] != 'afventer':
        try:
            pct_str = h['udfald'].replace('+', '').replace('%', '').strip()
            for emoji in ['\u2705', '\u274c', ' ']:
                pct_str = pct_str.replace(emoji, '')
            pct = float(pct_str.strip())
            afkast[h['ticker']].append(pct)
        except:
            pass

afkast_liste = [(ticker, sum(v)/len(v), len(v)) for ticker, v in afkast.items() if len(v) >= 3]
afkast_liste.sort(key=lambda x: x[1], reverse=True)
print("\nTop 10 bedste gennemsnitligt afkast:")
for ticker, snit, antal in afkast_liste[:10]:
    print(f"  {ticker}: {snit:+.1f}% snit ({antal} handler)")
print("\nTop 10 daarligste gennemsnitligt afkast:")
for ticker, snit, antal in afkast_liste[-10:]:
    print(f"  {ticker}: {snit:+.1f}% snit ({antal} handler)")
