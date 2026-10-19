"""検証15：新高値ブレイク銘柄の追加と半導体連動銘柄の除外（後出しなし）
検証13：急落しにくい銘柄の選定（銘柄の急落リスク＋市場の暴落リスク）。土台は検証6・7
検証7：直近の損失の原因分析＋後出しなしの改善条件探し（検証6の土台を流用）
検証6：後出しチェック（前半で条件を選び、後半で試す）＋現実のコスト
前半（学習）：2021-10〜2023-12　後半（試験）：2024-01〜2026-10
コスト：
- 約定の厳しさ：翌日の安値が指値より0.2%以上下がった時だけ約定（触れただけは不成立）
- 値段のずれ：買いは0.1%高く、売りは0.1%安く約定
- ETFの乗り換え：売り買いの度に0.05%
- 税金：年間の売買益がプラスなら20.315%（ETF側の値上がり益は売らないので非課税扱い）
条件の候補：売買代金 10/30/50/100/200億円 × VIXで買い停止 あり/なし"""
import json
import pandas as pd
from core import plan, add_indicators, CAPITAL, MAX_POSITIONS
from data import load
import strategy
from strategy import is_breakout
from risk import factors, risk_off

SPLIT = pd.Timestamp("2024-01-01")
SLIP, ETF_FEE, TAX, FILL = 0.001, 0.0005, 0.20315, 0.998

U = json.load(open("data/universe_all.json", encoding="utf-8"))
raw = load("5y", codes=list(U), size=50, wait=10)
frames = {}
for c, df in raw.items():
    df = df.copy(); df.index = pd.to_datetime(df.index).tz_localize(None)
    frames[c] = add_indicators(df)
F = factors("6y")
roff = {d: risk_off(F.loc[d]) for d in F.index}
at = lambda d: F.index[max(F.index.searchsorted(d, side="right") - 1, 0)]
start = max(min(d.index[0] for d in frames.values()) + pd.Timedelta(days=130), F.index[0])
print("銘柄", len(frames), "開始", start.date())


def sim(d, i, p, max_hold=60):
    """厳しめの約定と値段のずれを入れた売買"""
    n = len(d)
    if i + 1 >= n or d.Low.iloc[i + 1] > p["entry"] * FILL:
        return None
    buy = min(d.Open.iloc[i + 1], p["entry"]) * (1 + SLIP)
    for k in range(i + 1, min(i + 1 + max_hold, n)):
        r = d.iloc[k]
        if r.Low <= p["stop"]:
            px = r.Open if (k > i + 1 and r.Open < p["stop"]) else p["stop"]
            return buy, px * (1 - SLIP), k, "損切り"
        if r.Close < r.sma25 and k + 1 < n:
            return buy, d.Open.iloc[k + 1] * (1 - SLIP), k + 1, "25日線割れ"
    if i + max_hold < n:
        return buy, d.Close.iloc[i + max_hold] * (1 - SLIP), i + max_hold, "期限"
    return None




import numpy as np, yfinance as yf
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
strategy.MIN_TURNOVER = 100e8
def gy(s):
    x = yf.download(s, start="2019-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return x
n225 = F["n225"]; sox = gy("^SOX"); vix = gy("^VIX"); vix3 = gy("^VIX3M")
nkr = n225.pct_change(); soxr = sox.pct_change()
def before(s, dt):
    i = s.index.searchsorted(dt, side="right") - 1
    return float(s.iloc[i]) if i >= 0 else np.nan
pool = []
for code, d in frames.items():
    rr = d.Close.pct_change()
    for i in range(86, len(d)):
        if d.index[i] < start or not is_breakout(d, i):
            continue
        p = plan(d.Close.iloc[i], d.atr.iloc[i])
        if not p: continue
        s = sim(d, i, p)
        if not s: continue
        buy, sell, k, why = s
        r = d.iloc[i]; dt = d.index[i]
        w = rr.iloc[i-59:i+1]; m = nkr.reindex(w.index); sx = soxr.reindex(w.index, method="ffill")
        beta_nk = float(w.cov(m) / m.var()) if m.var() > 0 else np.nan
        beta_sox = float(w.cov(sx) / sx.var()) if sx.var() > 0 else np.nan
        lo5 = float(d.Low.iloc[i+1:i+6].min()) / buy - 1 if i + 1 < len(d) else np.nan
        nn = n225[n225.index <= dt]
        pool.append({"date": dt, "code": code, "shares": p["shares"], "cost": p["entry"] * p["shares"], "buy": buy, "sell": sell,
            "entry_date": d.index[i + 1], "exit_date": d.index[k], "why": why, "pnl": (sell - buy) * p["shares"], "ret": sell / buy - 1,
            "crash": int(lo5 <= -0.10), "lo5": lo5,
            "atrp": float(r.atr / r.Close), "ext": float(r.Close / r.sma25 - 1), "r1": float(rr.iloc[i]),
            "r5": float(r.Close / d.Close.iloc[i - 5] - 1), "r20": float(r.Close / d.Close.iloc[i - 20] - 1),
            "vr": float(r.Volume / r.vol20), "to": float(np.log(r.turnover20)),
            "hi250": float(r.Close / d.High.iloc[max(0, i-250):i+1].max() - 1),
            "upstreak": int((rr.iloc[i-4:i+1] > 0).sum()), "vol20": float(rr.iloc[i-19:i+1].std() * np.sqrt(252)),
            "beta_nk": beta_nk, "beta_sox": beta_sox, "corr_sox": float(w.corr(sx)), "newhi": bool(r.Close > d.High.iloc[max(0,i-250):i].max()) and i >= 250,
            "mkt5": float(nn.iloc[-1] / nn.iloc[-6] - 1), "mkt_ma25": float(nn.iloc[-1] / nn.tail(25).mean() - 1),
            "sox1": before(soxr, dt), "term": before(vix, dt) / before(vix3, dt)})
pool.sort(key=lambda t: (t["date"], -t["vr"]))
pool = [t for t in pool if not roff[at(t["date"])]]
print("候補", len(pool))
FE = ["atrp", "ext", "r1", "r5", "r20", "vr", "to", "hi250", "upstreak", "vol20", "beta_nk", "beta_sox", "mkt5", "mkt_ma25", "sox1", "term"]
def run(flt, a, b):
    trades, open_pos = [], []
    for t in pool:
        if not (a <= t["date"] < b) or not flt(t):
            continue
        open_pos = [o for o in open_pos if o["exit_date"] > t["date"]]
        used = sum(o["buy"] * o["shares"] for o in open_pos)
        if (len(open_pos) >= MAX_POSITIONS or used + t["cost"] > CAPITAL
                or any(o["code"] == t["code"] for o in open_pos)):
            continue
        open_pos.append(t); trades.append(t)
    n = n225[(n225.index >= a) & (n225.index < b)]
    ret = n.pct_change().fillna(0)
    buys, sells = {}, {}
    for t in trades:
        buys.setdefault(t["entry_date"], []).append(t); sells.setdefault(t["exit_date"], []).append(t)
    idle, held, eq, yr, prev_y = float(CAPITAL), [], [], {}, None
    for dt, r in ret.items():
        if prev_y is not None and dt.year != prev_y:
            idle -= max(0.0, yr.get(prev_y, 0.0)) * TAX
        prev_y = dt.year
        idle *= 1 + float(r)
        for t in buys.get(dt, []):
            c = t["buy"] * t["shares"]; idle -= c * (1 + ETF_FEE); held.append(t)
        for t in sells.get(dt, []):
            v = t["sell"] * t["shares"]; idle += v * (1 - ETF_FEE)
            held = [h for h in held if h is not t]; yr[dt.year] = yr.get(dt.year, 0.0) + t["pnl"]
        eq.append(idle + sum(float(frames[h["code"]].Close.asof(dt)) * h["shares"] for h in held))
    eq[-1] -= max(0.0, yr.get(prev_y, 0.0)) * TAX
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v); mdd = min(mdd, v - peak)
    bench = CAPITAL * (float(n.iloc[-1]) / float(n.iloc[0]) - 1)
    w = [t for t in trades if t["pnl"] > 0]
    gp = sum(t["pnl"] for t in w); gl = -sum(t["pnl"] for t in trades if t["pnl"] <= 0)
    return {"vs": round(eq[-1] - CAPITAL - bench), "n": len(trades), "hit": len(w),
            "pf": round(gp / gl, 2) if gl else None, "mdd": round(mdd)}



END = n225.index[-1] + pd.Timedelta(days=1)
P = pd.DataFrame(pool)
tr, te = P[P.date < SPLIT], P[P.date >= SPLIT]
L = [f"候補 {len(P)}件（学習 {len(tr)} / 試験 {len(te)}）。新高値＝終値が過去250営業日の高値超え", 
     f"新高値の割合：{P.newhi.mean()*100:.1f}% / 半導体連動（SOXとの相関）中央値 {P.corr_sox.median():.2f}", ""]
for lab, g in (("新高値", te[te.newhi]), ("60日高値のみ", te[~te.newhi])):
    w = (g.pnl > 0).mean(); gp = g.pnl[g.pnl > 0].sum(); gl = -g.pnl[g.pnl <= 0].sum()
    L.append(f"試験 {lab}：{len(g)}件 勝率{w*100:.1f}% PF{gp/gl if gl else 0:.2f} 平均{g.ret.mean()*100:+.2f}% 急落率{g.crash.mean()*100:.1f}%")
for th in (0.3, 0.4, 0.5):
    for lab, g in ((f"SOX相関≧{th}", te[te.corr_sox >= th]), (f"SOX相関<{th}", te[te.corr_sox < th])):
        w = (g.pnl > 0).mean(); gp = g.pnl[g.pnl > 0].sum(); gl = -g.pnl[g.pnl <= 0].sum()
        L.append(f"試験 {lab}：{len(g)}件 勝率{w*100:.1f}% PF{gp/gl if gl else 0:.2f} 平均{g.ret.mean()*100:+.2f}% 急落率{g.crash.mean()*100:.1f}%")
L.append("")
base_pool = list(pool)
def run_with(order_newhi, flt):
    global pool
    pool = sorted(base_pool, key=lambda t: (t["date"], 0 if (order_newhi and t["newhi"]) else 1, -t["vr"]))
    a, b = run(flt, start, SPLIT), run(flt, SPLIT, END)
    pool = base_pool
    return a, b
cfgs = [("今の方式", False, lambda t: True), ("新高値を優先", True, lambda t: True), ("新高値のみ", False, lambda t: t["newhi"])]
for th in (0.3, 0.4, 0.5):
    cfgs += [(f"半導体連動（SOX相関≧{th}）を除外", False, lambda t, th=th: not (t["corr_sox"] >= th)),
             (f"新高値を優先＋SOX相関≧{th}を除外", True, lambda t, th=th: not (t["corr_sox"] >= th)),
             (f"新高値のみ＋SOX相関≧{th}を除外", False, lambda t, th=th: t["newhi"] and not (t["corr_sox"] >= th))]
res = [(nm,) + run_with(o, f) for nm, o, f in cfgs]
b0a, b0b = res[0][1], res[0][2]
L.append("## 条件ごと（学習 2022-2023 → 試験 2024-）日経比と基準比")
for nm, a, b in sorted(res, key=lambda x: -x[1]["vs"]):
    L.append(f"- {nm}：学習 日経比 {a['vs']:+,}（基準比 {a['vs']-b0a['vs']:+,}） → 試験 日経比 {b['vs']:+,}（基準比 {b['vs']-b0b['vs']:+,}）取引{b['n']} PF{b['pf']} 最大落ち込み{b['mdd']:,}")
best = max(res[1:], key=lambda x: x[1]["vs"])
L.append(f"\n学習で一番良かった：{best[0]} → 試験の基準比 {best[2]['vs']-b0b['vs']:+,} → {'予測出来た' if best[2]['vs'] > b0b['vs'] else '予測出来なかった'}")
both = [x for x in res[1:] if x[1]['vs'] > b0a['vs'] and x[2]['vs'] > b0b['vs']]
L.append("学習・試験とも改善：" + ("、".join(f"{x[0]}（試験 {x[2]['vs']-b0b['vs']:+,}）" for x in both) or "なし"))
open("data/compare15.md", "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
