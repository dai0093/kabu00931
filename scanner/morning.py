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
    _, v3, _ = last2("^VIX3M")
    term = vc / v3
    # 検証11：単独指標で唯一、学習・試験とも成績がプラス（VIX÷VIX3M ≧ 1.06＝短期の恐怖が中期を上回る）
    if term >= 1.06:
        parts.append(f"【前日警戒】VIX÷VIX3M = {vc:.1f}÷{v3:.1f} = {term:.2f}（1.06以上）\n"
                     "検証11：翌日−2%以下の確率 普段5%→25%。今日15:25までに引けでETFを売り、明日の引けで買い戻す判断材料に")
        alert = alert or "term"
    sox1, vix1 = c / p - 1, vc / vp - 1
    fresh = (datetime.now(JST).date() - d).days <= 4
    line = f"前夜の米国（{d}）：SOX {sox1*100:+.1f}% / VIX {vc:.1f}（前日比 {vix1*100:+.0f}%）/ VIX÷VIX3M {term:.2f}"
    json.dump({"date": today, "us_date": str(d), "sox1": round(sox1, 4), "vix": round(vc, 2), "term": round(term, 3),
               "sox_alert": bool(fresh and sox1 <= -0.03), "term_alert": bool(term >= 1.06)},
              open("data/morning.json", "w"), ensure_ascii=False)
    if fresh and sox1 <= -0.03:
        alert = ("【暴落警戒】" + line + "\n検証8：この条件の日は日経の寄り〜大引けが平均で大きく下落。"
                 "寄り付きでETF・保有株を売り、大引けで買い戻す判断材料に（最終判断はご自身で）")
        parts.append(alert)
    else:
        parts.append(line + " → 暴落警戒なし")
except Exception as e:
    parts.append(f"前夜の米国市場の取得に失敗（{e}）")
ev_lines = []
try:
    import events
    ev_lines = events.upcoming(30)
    if ev_lines:
        parts.append("【今夜〜明朝の米国指標】（判断は今日15:25の引けまで）\n" + "\n".join(ev_lines)
                     + "\n※予想やナウキャストで上振れ／下振れの向きは当てられない（検証12）。逆指値で備える")
except Exception as e:
    parts.append(f"指標予定の取得に失敗（{e}）")
risk = s.get("risk", {})
if risk.get("off"):
    parts.append("市場リスク：リスクオフ中（新規の買いは停止）")
_w = (risk or {}).get("weak") or {}
if _w.get("on") and s.get("signals"):
    parts.append(f"【地合い注意・見送り推奨】日経5日騰落 {_w['n225_5d']*100:+.1f}%（検証7：見送りで成績改善）")
for t in s.get("signals", []):
    parts.append(f"【買い・指値】{t['name']}({t['code']}) {t['shares']}株\n"
                 f"指値 {t['entry']:,}円 → 約定したら損切り {t['stop']:,}円 の逆指値\n"
                 f"ETFを {t['cost']:,}円分 売って資金にする")
if s.get("etf_stop"):
    parts.append(f"【逆指値の確認】1321：{s['etf_stop']['stop']:,}円 以下で売り（寄り前に入っているか確認）")
for h in s.get("sells", []):
    parts.append(f"【売り・寄り】{h['name']}({h['code']})：{h.get('sell_signal','')}")
if s.get("market_date") and s["market_date"] >= today:
    parts.insert(0, "※判定が今日の日付です。場中の判定ではないか確認してください")
if s.get("signals") or s.get("sells") or risk.get("off") or alert or s.get("etf_stop") or ev_lines:
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
# run 2026-10-19_07:00:34
# run 2026-10-20 06:56 JST
# run 2026-10-21 06:57 JST
# run 2026-10-22 06:56
# run 2026-10-23 06:57 JST
# run 2026-10-26 06:57 JST
# run 2026-10-27 06:56 JST
# run 2026-10-28 06:57 JST
# run 2026-10-28 07:06 JST
# run 2026-10-29 06:56 JST
