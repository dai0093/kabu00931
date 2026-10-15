"""朝のリマインド（平日 5:37〜7:23 JST に4回起動、最初の1回だけ送る）。
前日夕方の判定から「今日出す注文」と、前夜の米国市場から「暴落警戒」を通知する。
暴落警戒（検証8で採用）：米SOX指数の前夜騰落が −3%以下
  試験期間2017-2026：日経−3%以下の暴落40日のうち22日（55%）で事前に警告。警告175日のうち暴落は13%"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
TOPIC = os.environ.get("NTFY_TOPIC", "")
s = json.load(open("data/signals.json", encoding="utf-8"))
today = datetime.now(JST).strftime("%Y-%m-%d")
SENT = "data/morning_sent.txt"
if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and os.path.exists(SENT) \
        and open(SENT).read().strip() == today:
    print("今日は送信済み"); raise SystemExit(0)
parts, alert = [], None
try:
    import yfinance as yf
    def last2(sym):
        x = yf.download(sym, period="10d", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
        return x.index[-1].date(), float(x.iloc[-1]), float(x.iloc[-2])
    d, c, p = last2("^SOX"); vd, vc, vp = last2("^VIX")
    sox1, vix1 = c / p - 1, vc / vp - 1
    fresh = (datetime.now(JST).date() - d).days <= 4
    line = f"前夜の米国（{d}）：SOX {sox1*100:+.1f}% / VIX {vc:.1f}（前日比 {vix1*100:+.0f}%）"
    if fresh and sox1 <= -0.03:
        alert = ("【暴落警戒】" + line + "\n検証8：この条件の日は日経の寄り〜大引けが平均で大きく下落。"
                 "寄り付きでETF・保有株を売り、大引けで買い戻す判断材料に（最終判断はご自身で）")
        parts.append(alert)
    else:
        parts.append(line + " → 暴落警戒なし")
except Exception as e:
    parts.append(f"前夜の米国市場の取得に失敗（{e}）")
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
if s.get("signals") or s.get("sells") or risk.get("off") or alert:
    body = "\n\n".join(parts)
    title = f"今日の注文（{s.get('market_date')}終値で判定）"
else:
    body, title = "\n\n".join(parts + ["今日出す注文はありません。ETFのまま保有"]), f"今日の注文なし（{s.get('market_date')}終値で判定）"
print(title); print(body)
if TOPIC:
    if alert:
        title = "【暴落警戒】" + title
    q = urllib.parse.urlencode({"title": title, "priority": "5" if alert else "3",
                                "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}",
                           data=body.encode("utf-8"), method="POST"), timeout=30)
    open(SENT, "w").write(today)
