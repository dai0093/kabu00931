"""検証13：急落しにくい銘柄の選定（銘柄の急落リスク＋市場の暴落リスク）。土台は検証6・7
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
            "beta_nk": beta_nk, "beta_sox": beta_sox,
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
L = [f"候補 {len(P)}件（学習 {len(tr)} / 試験 {len(te)}）。急落＝買った後5日以内に安値が買値−10%以下",
     f"急落の割合：学習 {tr.crash.mean()*100:.1f}% / 試験 {te.crash.mean()*100:.1f}%", ""]
# 4493の判定時の値
for code, dt in (("4493", "2026-10-13"), ("4493", "2026-10-09"), ("2914", "2026-10-09"), ("4704", "2026-10-09"), ("9104", "2026-10-13")):
    x = P[(P.code == code) & (P.date == pd.Timestamp(dt))]
    if len(x):
        x = x.iloc[0]; L.append(f"{code} {dt}：" + " ".join(f"{k}={x[k]:.3g}" for k in FE) + f" → 急落{'あり' if x.crash else 'なし'}")
L.append("\n## ① 特徴ごとの急落率（試験期間、上位25%と下位25%）")
for f in FE:
    q1, q3 = tr[f].quantile(0.25), tr[f].quantile(0.75)
    lo, hi = te[te[f] <= q1], te[te[f] >= q3]
    L.append(f"- {f}：低い組 急落{lo.crash.mean()*100:.1f}%・平均{lo.ret.mean()*100:+.1f}% / 高い組 急落{hi.crash.mean()*100:.1f}%・平均{hi.ret.mean()*100:+.1f}%")
L.append("\n## ② 除外条件（学習期間の上位10%/5%を超える候補を除く）→ 試験期間の成績")
base_tr, base_te = run(lambda t: True, start, SPLIT), run(lambda t: True, SPLIT, END)
L.append(f"今の方式：学習 日経比 {base_tr['vs']:+,} / 試験 日経比 {base_te['vs']:+,} 取引{base_te['n']} PF{base_te['pf']} 最大落ち込み{base_te['mdd']:,} / 試験の急落率 {te.crash.mean()*100:.1f}%")
res = []
for f in FE:
    for q in (0.90, 0.95):
        for side in ("hi", "lo"):
            th = tr[f].quantile(q if side == "hi" else 1 - q)
            fl = (lambda t, f=f, th=th: not (t[f] >= th)) if side == "hi" else (lambda t, f=f, th=th: not (t[f] <= th))
            a, b = run(fl, start, SPLIT), run(fl, SPLIT, END)
            kept = te[[fl(t) for t in te.to_dict("records")]]
            res.append((f"{f} {'≧' if side=='hi' else '≦'}{th:.3g} を除く", a["vs"] - base_tr["vs"], b["vs"] - base_te["vs"], b, kept.crash.mean()))
res.sort(key=lambda x: -x[1])
for nm, da, db, b, cr in res[:15]:
    L.append(f"- {nm}：学習 {da:+,} → 試験 {db:+,}（基準比）／試験の急落率 {cr*100:.1f}%／PF{b['pf']}／最大落ち込み{b['mdd']:,}")
both = [x for x in res if x[1] > 0 and x[2] > 0]
L.append("学習・試験とも改善：" + ("、".join(f"{x[0]}（{x[2]:+,}）" for x in both[:8]) or "なし"))
best = res[0]
L.append(f"学習で一番良かった：{best[0]} → 試験 {best[2]:+,} → {'予測出来た' if best[2] > 0 else '予測出来なかった'}")

L.append("\n## ③ 急落予測モデル（全特徴のロジスティック回帰。年ごとに過去だけで学習）")
prob = pd.Series(np.nan, index=P.index)
for Y in range(2023, P.date.max().year + 1):
    trn = P[P.date < pd.Timestamp(Y, 1, 1)]; tst = P[(P.date >= pd.Timestamp(Y, 1, 1)) & (P.date < pd.Timestamp(Y + 1, 1, 1))]
    if len(tst) == 0 or trn.crash.sum() < 10: continue
    med = trn[FE].median()
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=3000, class_weight="balanced")).fit(trn[FE].fillna(med), trn.crash)
    prob[tst.index] = m.predict_proba(tst[FE].fillna(med))[:, 1]
    if Y == P.date.max().year:
        coef = pd.Series(m[-1].coef_[0], index=FE).sort_values(key=abs, ascending=False)
        thr_by = {q: float(np.quantile(m.predict_proba(trn[FE].fillna(med))[:, 1], q)) for q in (0.7, 0.8, 0.9)}
        fm, fmed = m, med
g = P[prob.notna()]; pg = prob[g.index]
L.append(f"2023〜の予測精度 AUC {roc_auc_score(g.crash, pg):.3f}（0.5=当てずっぽう）")
L.append("効いている特徴（＋は急落しやすい）：" + "、".join(f"{k}{v:+.2f}" for k, v in coef.items()))
for q in (0.7, 0.8, 0.9):
    th = thr_by[q]
    keep_ids = set(g.index[pg < th])
    fl = lambda t, ids=keep_ids: True
    gg = g[pg < th]; dr = g[pg >= th]
    L.append(f"- 急落確率が上位{int((1-q)*100)}%の候補を除く：残す{len(gg)}件 急落率 {gg.crash.mean()*100:.1f}%・平均{gg.ret.mean()*100:+.2f}% / 除いた{len(dr)}件 急落率 {dr.crash.mean()*100:.1f}%・平均{dr.ret.mean()*100:+.2f}%")
    keys = {(t.date, t.code) for t in gg.itertuples()}
    b = run(lambda t, keys=keys: (t["date"], t["code"]) in keys, pd.Timestamp("2023-01-01"), END)
    b0 = run(lambda t: True, pd.Timestamp("2023-01-01"), END)
    L.append(f"   2023〜の日経比：今の方式 {b0['vs']:+,} → 除外後 {b['vs']:+,}（差 {b['vs']-b0['vs']:+,}）PF {b0['pf']}→{b['pf']} 最大落ち込み {b0['mdd']:,}→{b['mdd']:,}")
for code, dt in (("4493", "2026-10-13"), ("4493", "2026-10-09")):
    x = P[(P.code == code) & (P.date == pd.Timestamp(dt))]
    if len(x) and not np.isnan(prob[x.index[0]]):
        L.append(f"{code} {dt} の急落確率 {prob[x.index[0]]*100:.1f}%（除外ライン 上位20%={thr_by[0.8]*100:.1f}%）")
import pickle; pickle.dump({"model": fm, "med": fmed, "FE": FE, "thr": thr_by}, open("data/crash_model.pkl", "wb"))
open("data/compare13.md", "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
