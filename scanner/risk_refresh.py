"""朝（米国市場の終了後）に signals.json の市場リスク欄だけを最新化する。
前日夕方（16:27 JST）の判定時点では米国の当日終値が未確定のため、VIX等が1日古くなるのを防ぐ。"""
import json
import pandas as pd  # noqa: F401
from datetime import datetime, timezone, timedelta
from risk import snapshot

P = "data/signals.json"
s = json.load(open(P, encoding="utf-8"))
_, r = snapshot("1y")
r["weak"] = (s.get("risk") or {}).get("weak")
r["refreshed"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
s["risk"] = r
json.dump(s, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("市場リスク更新", r["date"], "VIX", r["values"]["vix"], "リスクオフ" if r["off"] else "平常")
