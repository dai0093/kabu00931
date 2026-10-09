"""毎営業日の判定（高値更新方式＋待機資金は日経平均ETF）。
- 買い候補：data/signals.json に書き、スマホへ通知
- 過去の候補：保有中なら毎日「売るべきか」を判定し、売り指示も通知
- 成否（予測出来た／出来なかった）は data/history.json で追跡"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from core import add_indicators, plan
from data import load, universe
import strategy
strategy.MIN_TURNOVER = 100e8   # 検証3で日経に勝った基準：20日平均売買代金100億円以上
from strategy import is_breakout, simulate_trend
from universe import STOCKS
from holdings import HELD

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # GitHubのSecretから読む
APP_URL = "https://dai0093.github.io/kabu00931/signals.html"
JST = timezone(timedelta(hours=9))
os.makedirs("data", exist_ok=True)

NAMES = universe()
prices = load("1y", adjust=False)   # 証券会社の画面と同じ「実際の株価」（配当調整なし）
# 場中（15:45より前）に動いた場合は、未確定の当日足を捨てて前日の確定足で判定する
_now = datetime.now(JST)
if _now.hour * 60 + _now.minute < 15 * 60 + 45:
    _today = _now.strftime("%Y-%m-%d")
    prices = {c: df[df.index.strftime("%Y-%m-%d") < _today] for c, df in prices.items()}
frames = {c: add_indicators(df) for c, df in prices.items()}
last_date = max(str(d.index[-1].date()) for d in frames.values())

# 1) 今日の買い候補
today = []
for code, d in frames.items():
    i = len(d) - 1
    if str(d.index[i].date()) != last_date or not is_breakout(d, i):
        continue
    p = plan(d.Close.iloc[i], d.atr.iloc[i])
    if p:
        today.append({"date": last_date, "code": code, "name": NAMES.get(code, code),
                      "vol_ratio": round(float(d.Volume.iloc[i] / d.vol20.iloc[i]), 2), **p})
today.sort(key=lambda t: -t["vol_ratio"])
today = today[:5]

# 2) 過去候補の追跡と売り判定
hist_path = "data/history.json"
history = json.load(open(hist_path, encoding="utf-8")) if os.path.exists(hist_path) else []
history = [h for h in history if h.get("method") == "高値更新"]  # 旧方式の記録は除外
known = {(h["date"], h["code"]) for h in history}
history += [dict(t, method="高値更新") for t in today if (t["date"], t["code"]) not in known]

sells, quotes = [], {}
for h in history:
    d = frames.get(h["code"])
    if d is None or h.get("status") in ("closed", "unfilled"):
        continue
    idx = [k for k, x in enumerate(d.index) if str(x.date()) == h["date"]]
    if not idx:
        continue
    h.update(simulate_trend(d, idx[0], h))
    last = d.iloc[-1]
    if h.get("status") == "open":
        if last.Close < last.sma25:
            h["sell_signal"] = "終値が25日線を割った → 明日の寄りで売り"
            sells.append(h)
        else:
            h.pop("sell_signal", None)
# 保有銘柄（主要93に無いもの）を追加取得
import yfinance as yf
_extra = [c for c in HELD if c not in frames]
if _extra:
    _raw = yf.download([f"{c}.T" for c in _extra], period="1y", group_by="ticker",
                       auto_adjust=False, progress=False)
    for c in _extra:
        try:
            frames[c] = add_indicators(_raw[f"{c}.T"].dropna(subset=["Close"]))
        except Exception as e:
            print(c, "取得失敗", e)

# 保有銘柄の売り判定（終値が25日線を割ったら翌日寄りで売り）
held_sells = []
for c, nm in HELD.items():
    d = frames.get(c)
    if d is None or len(d) < 26:
        continue
    r = d.iloc[-1]
    if r.Close < r.sma25:
        held_sells.append({"code": c, "name": nm, "close": round(float(r.Close)),
                           "sma25": round(float(r.sma25))})

# ダッシュボード用：全銘柄の最新終値と25日線（保有株の損益・売り判定に使う）
for code, d in frames.items():
    last = d.iloc[-1]
    quotes[code] = {"close": round(float(last.Close)), "sma25": round(float(last.sma25)),
                    "atr": round(float(last.atr), 1)}
json.dump(history, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

closed = [h for h in history if h.get("status") == "closed"]
track = {"closed": len(closed), "hit": sum(h["hit"] for h in closed),
         "pnl": round(sum(h["pnl"] for h in closed))}
out = {"updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
       "market_date": last_date, "method": "高値更新（売買代金100億円以上・東証全銘柄）＋待機資金は日経平均ETF",
       "signals": today, "sells": sells, "held_sells": held_sells, "held": HELD, "quotes": quotes, "track": track,
       "open": [h for h in history if h.get("status") == "open"]}
json.dump(out, open("data/signals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ダッシュボード用ローソク足（直近90営業日）：全銘柄＋保有銘柄＋ETF(1321)＋日経平均
def _bars(df):
    df = df.tail(90)
    return [[str(x.date()), round(float(r.Open), 1), round(float(r.High), 1),
             round(float(r.Low), 1), round(float(r.Close), 1)] for x, r in df.iterrows()]
# 表示に使う銘柄だけ（候補・保有・主要93）に絞ってファイルを軽くする
_show = set(STOCKS) | set(HELD) | {t["code"] for t in today} | {h["code"] for h in history}
candles = {c: _bars(d) for c, d in frames.items() if c in _show}
for sym, key in (("1321.T", "1321"), ("^N225", "N225")):
    try:
        x = yf.download(sym, period="6mo", auto_adjust=False, progress=False)
        x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
        candles[key] = _bars(x.dropna(subset=["Close"]))
    except Exception as e:
        print(sym, "取得失敗", e)
names = dict(NAMES, **HELD, **{"1321": "日経225ETF", "N225": "日経平均"})
json.dump({"names": names, "candles": candles},
          open("data/candles.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

# 3) 通知
if not NTFY_TOPIC:
    print("NTFY_TOPIC未設定のため通知をスキップ")
    raise SystemExit(0)
parts = []
for t in today:
    parts.append(f"【買い】{t['name']}({t['code']}) {t['shares']}株\n"
                 f"指値 {t['entry']:,}円 / 損切り {t['stop']:,}円\n"
                 f"ETFを {t['cost']:,}円分 売って資金にする\n"
                 f"売り：損切りか、終値が25日線を割った翌日の寄り")
for h in sells:
    parts.append(f"【売り】{h['name']}({h['code']})\n{h['sell_signal']}\n売った代金はETFに戻す")
for h in []:  # 保有株への25日線ルールは検証で「予測出来なかった」ため通知しない（held_check参照）
    parts.append(f"【保有株・売り】{h['name']}({h['code']})\n終値 {h['close']:,}円 が25日線 {h['sma25']:,}円 を下回った → 明日の寄りで売り")
if parts:
    body = "\n\n".join(parts)
    title = f"買い{len(today)}件・売り{len(sells)}件（{last_date}）"
else:
    body, title = "本日は売買なし。ETFのまま保有", f"判定完了（{last_date}）"
q = urllib.parse.urlencode({"title": title, "click": APP_URL})
req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}?{q}",
                             data=body.encode("utf-8"), method="POST")
urllib.request.urlopen(req, timeout=30)
print(title)
print(body)
