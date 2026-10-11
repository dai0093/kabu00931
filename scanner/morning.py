"""朝のリマインド（平日 7:53 JST）。前日夕方の判定から「今日出す注文」をまとめて通知する。"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
TOPIC = os.environ.get("NTFY_TOPIC", "")
s = json.load(open("data/signals.json", encoding="utf-8"))
today = datetime.now(JST).strftime("%Y-%m-%d")
parts = []
risk = s.get("risk", {})
if risk.get("off"):
    parts.append("市場リスク：リスクオフ中（新規の買いは停止）")
for t in s.get("signals", []):
    parts.append(f"【買い・指値】{t['name']}({t['code']}) {t['shares']}株\n"
                 f"指値 {t['entry']:,}円 → 約定したら損切り {t['stop']:,}円 の逆指値\n"
                 f"ETFを {t['cost']:,}円分 売って資金にする")
for h in s.get("sells", []):
    parts.append(f"【売り・寄り】{h['name']}({h['code']})：{h.get('sell_signal','')}")
if s.get("market_date") and s["market_date"] >= today:
    parts.insert(0, "※判定が今日の日付です。場中の判定ではないか確認してください")
if parts:
    body = "\n\n".join(parts)
    title = f"今日の注文（{s.get('market_date')}終値で判定）"
else:
    body, title = "今日出す注文はありません。ETFのまま保有", f"今日の注文なし（{s.get('market_date')}終値で判定）"
print(title); print(body)
if TOPIC:
    q = urllib.parse.urlencode({"title": title, "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}",
                           data=body.encode("utf-8"), method="POST"), timeout=30)
