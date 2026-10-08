"""毎営業日の判定。買い候補を data/signals.json に書き、スマホへ通知する。
過去に出した候補の成否（予測出来た／出来なかった）も data/history.json で追跡する。"""
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from core import add_indicators, is_signal, plan, simulate
from data import load
from universe import STOCKS

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # GitHubのSecretから読む
JST = timezone(timedelta(hours=9))
os.makedirs("data", exist_ok=True)

prices = load("1y")
frames = {c: add_indicators(df) for c, df in prices.items()}
last_date = max(str(d.index[-1].date()) for d in frames.values())

# 1) 今日の買い候補
today = []
for code, d in frames.items():
    i = len(d) - 1
    if str(d.index[i].date()) != last_date or not is_signal(d, i):
        continue
    p = plan(d.Close.iloc[i], d.atr.iloc[i])
    if p:
        today.append({"date": last_date, "code": code, "name": STOCKS[code],
                      "vol_ratio": round(float(d.Volume.iloc[i] / d.vol20.iloc[i]), 2), **p})
today.sort(key=lambda t: -t["vol_ratio"])
today = today[:5]

# 2) 過去候補の追跡
hist_path = "data/history.json"
history = json.load(open(hist_path, encoding="utf-8")) if os.path.exists(hist_path) else []
known = {(h["date"], h["code"]) for h in history}
history += [dict(t) for t in today if (t["date"], t["code"]) not in known]
for h in history:
    if h.get("status") in ("closed", "unfilled"):
        continue
    d = frames.get(h["code"])
    if d is None:
        continue
    idx = [k for k, x in enumerate(d.index) if str(x.date()) == h["date"]]
    if idx:
        h.update(simulate(d, idx[0], h))
json.dump(history, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

closed = [h for h in history if h.get("status") == "closed"]
track = {"closed": len(closed), "hit": sum(h["hit"] for h in closed),
         "pnl": round(sum(h["pnl"] for h in closed))}

out = {"updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
       "market_date": last_date, "signals": today, "track": track,
       "open": [h for h in history if h.get("status") == "open"]}
json.dump(out, open("data/signals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 3) 通知
if not NTFY_TOPIC:
    print("NTFY_TOPIC未設定のため通知をスキップ")
    raise SystemExit(0)
if today:
    body = "\n\n".join(
        f"{t['name']}({t['code']}) {t['shares']}株\n"
        f"指値 {t['entry']:,}円 / 損切り {t['stop']:,}円 / 利確 {t['target']:,}円\n"
        f"投入 {t['cost']:,}円 / 最大損失 {t['risk_yen']:,}円" for t in today)
    title = f"買い候補 {len(today)}件（{last_date}終値ベース）"
else:
    body, title = "本日は買い候補なし", f"判定完了（{last_date}）"
import urllib.parse
q = urllib.parse.urlencode({"title": title,
                            "click": "https://dai0093.github.io/kabu00931/signals.html"})
req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}?{q}", data=body.encode("utf-8"),
                             method="POST")
urllib.request.urlopen(req, timeout=30)
print(title)
print(body)
