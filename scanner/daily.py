"""毎営業日の判定（高値更新方式＋待機資金は日経平均ETF）。
- 買い候補：data/signals.json に書き、スマホへ通知
- 過去の候補：保有中なら毎日「売るべきか」を判定し、売り指示も通知
- 成否（予測出来た／出来なかった）は data/history.json で追跡"""
import json
import pandas as pd
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
from private import holdings, encrypt
_H = holdings()                       # Secret「HOLDINGS」から（公開リポジトリには置かない）
HELD = {c: v[0] for c, v in _H.items()}

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

# 定時実行は1日3回（遅延対策）。同じ終値で判定済みなら、2回目以降は何もしない（休日も同じ理由で停止）
try:
    _prev = json.load(open("data/signals.json", encoding="utf-8"))
except Exception:
    _prev = {}
if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and _prev.get("market_date") == last_date \
        and _prev.get("final"):
    print("判定済みのためスキップ", last_date)
    raise SystemExit(0)

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
# 急落予測（検証13）：5日以内に−10%以上の急落確率が除外ライン以上の候補は外す（上位5件に絞る前に判定）
crash_out = []
try:
    import crashrisk
    from risk import factors as _fac
    crashrisk.score(today, frames, _fac("1y")["n225"].dropna())
    crash_out = [t for t in today if t.get("crash_out")]
    today = [t for t in today if not t.get("crash_out")]
except Exception as e:
    import traceback; print("急落予測の失敗", traceback.format_exc())
today = today[:5]

# 市場リスク連携（検証4で採用：リスクオフ中は新規の買いを止める）
from risk import factors, state as risk_state, risk_off
risk = {"off": False}
try:
    from risk import snapshot
    _F, risk = snapshot("1y")
except Exception as e:
    print("リスク指標の取得失敗", e)
# 地合いの注意（検証7：日経5日騰落が0%以上の時だけ買う → 前半+301,379円・後半+1,465,745円 改善）
weak = None
try:
    _n = _F["n225"].dropna()
    _n5 = float(_n.iloc[-1] / _n.iloc[-6] - 1)
    weak = {"n225_5d": round(_n5, 4), "on": _n5 < 0, "last": round(float(_n.iloc[-1])), "prev5": round(float(_n.iloc[-6]))}
except Exception as e:
    print("日経5日騰落の計算失敗", e)
risk["weak"] = weak
blocked = []
if risk.get("off"):
    blocked, today = today, []

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

# ダッシュボード用：監視対象の最新終値と25日線（保有株だけの銘柄は公開ファイルに出さない）
for code, d in frames.items():
    if code in _extra:
        continue
    last = d.iloc[-1]
    quotes[code] = {"close": round(float(last.Close)), "sma25": round(float(last.sma25)),
                    "atr": round(float(last.atr), 1)}
# 全銘柄・保有株の急落確率（検証13のモデル。保有株への当てはまりは検証14で確認）
try:
    import crashrisk
    from risk import factors as _fac2
    _cr = [{"code": c} for c, d in frames.items() if len(d) >= 90 and str(d.index[-1].date()) == last_date]
    crashrisk.score(_cr, frames, _fac2("1y")["n225"].dropna())
    CRASH = {t["code"]: t for t in _cr}
    for c, q in quotes.items():
        if c in CRASH: q["crash_p"] = CRASH[c]["crash_p"]; q["crash_why"] = CRASH[c]["crash_why"]
except Exception:
    import traceback; print("保有株の急落確率の失敗", traceback.format_exc()); CRASH = {}
json.dump(history, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

closed = [h for h in history if h.get("status") == "closed"]
track = {"closed": len(closed), "hit": sum(h["hit"] for h in closed),
         "pnl": round(sum(h["pnl"] for h in closed))}
out = {"final": last_date < datetime.now(JST).strftime("%Y-%m-%d") or datetime.now(JST).hour * 60 + datetime.now(JST).minute >= 15 * 60 + 45,
       "risk": risk, "blocked": blocked, "updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
       "market_date": last_date, "method": "高値更新（売買代金100億円以上・東証全銘柄）＋待機資金は日経平均ETF",
       "signals": today, "crash_out": crash_out, "sells": sells, "quotes": quotes, "track": track,
       "open": [h for h in history if h.get("status") == "open"],
       # 直近5営業日の候補：翌日以降に買った場合も購入記録を入力できるようにする
       "recent": [h for h in history if h["date"] in sorted({x["date"] for x in history})[-5:]]}
json.dump(out, open("data/signals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ダッシュボード用ローソク足（直近90営業日）：全銘柄＋保有銘柄＋ETF(1321)＋日経平均
def _bars(df):
    df = df.tail(90)
    return [[str(x.date()), round(float(r.Open), 1), round(float(r.High), 1),
             round(float(r.Low), 1), round(float(r.Close), 1)] for x, r in df.iterrows()]
# 表示に使う銘柄だけ（候補・保有・主要93）に絞ってファイルを軽くする
_show = set(STOCKS) | {t["code"] for t in today} | {h["code"] for h in history}
candles = {c: _bars(d) for c, d in frames.items() if c in _show}
for sym, key in (("1321.T", "1321"), ("^N225", "N225")):
    try:
        x = yf.download(sym, period="6mo", auto_adjust=False, progress=False)
        x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
        candles[key] = _bars(x.dropna(subset=["Close"]))
    except Exception as e:
        print(sym, "取得失敗", e)
# 株式分割の履歴（直近1年）：保有株の取得単価・株数を分割後に直すために使う
splits = {}
for c in sorted(_show):
    try:
        sp = yf.Ticker(f"{c}.T").splits
        sp = sp[sp.index >= pd.Timestamp.now(tz=sp.index.tz) - pd.Timedelta(days=365)] if len(sp) else sp
        if len(sp):
            splits[c] = [[str(i.date()), float(r)] for i, r in sp.items()]
    except Exception as e:
        print(c, "分割情報の取得失敗", e)
out["splits"] = splits
# 試運転：通知どおりに売買していたら、の成績
try:
    import paper
    json.dump(paper.build(history, frames), open("data/paper.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
except Exception:
    import traceback
    open("data/paper_error.txt", "w").write(traceback.format_exc())
    print("試運転の計算失敗", traceback.format_exc())
json.dump(out, open("data/signals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("splits", splits)

names = dict(NAMES, **{"1321": "日経225ETF", "N225": "日経平均"})
json.dump({"names": names, "candles": candles},
          open("data/candles.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

# 個人データ（保有銘柄・株数・株価・チャート・分割）は暗号化して保存
try:
    _priv = {"held": [], "candles": {}, "splits": {}, "etf_units": 0}
    for c, (nm, sh) in _H.items():
        if c == "1321":
            _priv["etf_units"] = sh
            continue
        d = frames.get(c)
        q = {"code": c, "name": nm, "shares": sh}
        if d is not None and len(d) > 1:
            q.update(close=round(float(d.Close.iloc[-1]), 1), prev=round(float(d.Close.iloc[-2]), 1),
                     sma25=round(float(d.sma25.iloc[-1]), 1))
            if c in CRASH:
                q.update(crash_p=CRASH[c]["crash_p"], crash_why=CRASH[c]["crash_why"])
            _priv["candles"][c] = _bars(d)
        _priv["held"].append(q)
        try:
            sp = yf.Ticker(f"{c}.T").splits
            sp = sp[sp.index >= pd.Timestamp.now(tz=sp.index.tz) - pd.Timedelta(days=365)] if len(sp) else sp
            if len(sp):
                _priv["splits"][c] = [[str(i.date()), float(r)] for i, r in sp.items()]
        except Exception:
            pass
    if _H:
        encrypt(_priv)
except Exception as e:
    print("個人データの暗号化に失敗", e)

# 3) 通知
if not NTFY_TOPIC:
    print("NTFY_TOPIC未設定のため通知をスキップ")
    raise SystemExit(0)
parts = []
if risk.get("off"):
    parts.append("【市場リスク】リスクオフ中のため新規の買いを停止"
                 f"（VIX {risk['values']['vix']}・HY OAS 20日変化 {risk['values']['hy_20']}pt）"
                 + (f"\n見送った候補：{'、'.join(t['name'] for t in blocked)}" if blocked else ""))
if weak and weak["on"] and today:
    parts.append(f"【地合い注意・見送り推奨】日経5日騰落 {weak['last']:,} ÷ {weak['prev5']:,} − 1 = {weak['n225_5d']*100:+.1f}%\n"
                 "検証7：マイナスの日の買いを見送ると成績が改善（前半+30万円・後半+147万円）。下の候補は買わない判断を推奨")
if crash_out:
    parts.append("【急落リスクで除外】" + "、".join(f"{t['name']}({t['code']}) 急落スコア{t['crash_p']*100:.0f}" for t in crash_out[:5])
                 + f"\n検証13：5日以内に−10%以上の急落確率が {crash_out[0]['crash_thr']*100:.0f}%以上の候補は除外")
for t in today:
    parts.append(f"【買い】{t['name']}({t['code']}) {t['shares']}株\n"
                 f"指値 {t['entry']:,}円 / 損切り {t['stop']:,}円\n"
                 + (f"急落スコア {t['crash_p']*100:.0f}（除外ライン {t['crash_thr']*100:.0f}）\n" if "crash_p" in t else "")
                 + f"ETFを {t['cost']:,}円分 売って資金にする\n"
                 f"売り：損切りか、終値が25日線を割った翌日の寄り")
for h in sells:
    parts.append(f"【売り】{h['name']}({h['code']})\n{h['sell_signal']}\n売った代金はETFに戻す")
for h in []:  # 保有株への25日線ルールは検証で「予測出来なかった」ため通知しない（held_check参照）
    parts.append(f"【保有株・売り】{h['name']}({h['code']})\n終値 {h['close']:,}円 が25日線 {h['sma25']:,}円 を下回った → 明日の寄りで売り")
# 明日の夜までの米国指標（検証12：事前予測値で向きは当てられないため、情報として表示）
try:
    import events
    _ev = events.upcoming(40)
    out["events"] = _ev
    if _ev:
        parts.append("【明日の夜までの米国指標】\n" + "\n".join(_ev))
except Exception as e:
    print("指標予定の取得失敗", e)
# 暴落よけ（検証10で採用）：ETF(1321)に前日終値 −1.5% の逆指値。発動したらその日の大引けで買い戻す
try:
    _e = candles["1321"][-1][4]
    _sp = int(_e * 0.985)
    out["etf_stop"] = {"close": _e, "stop": _sp}
    json.dump(out, open("data/signals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    parts.append(f"【暴落よけ・逆指値】日経225ETF(1321) 終値 {_e:,.0f}円 → 明日 {_sp:,}円 以下で売りの逆指値\n"
                 f"発動したら、その日の15:25までに引け成行で買い戻し")
except Exception as e:
    print("逆指値の計算失敗", e)
if parts:
    body = "\n\n".join(parts)
    title = f"買い{len(today)}件・売り{len(sells)}件・逆指値（{last_date}）"
else:
    body, title = "本日は売買なし。ETFのまま保有", f"判定完了（{last_date}）"
q = urllib.parse.urlencode({"title": title, "click": APP_URL})
req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}?{q}",
                             data=body.encode("utf-8"), method="POST")
urllib.request.urlopen(req, timeout=30)
print(title)
print(body)
# paper
# run 2026-10-13
# run private 18:47:03
# run 2026-10-14_21:06:44
# run 19:59:10
# run 2026-10-19_07:01:12
