"""検証7：直近の損失の原因分析＋後出しなしの改善条件探し（検証6の土台を流用）
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



import yfinance as yf
strategy.MIN_TURNOVER = 100e8
n225 = F["n225"]
pool = []
for code, d in frames.items():
    for i in range(86, len(d)):
        if d.index[i] < start or not is_breakout(d, i):
            continue
        p = plan(d.Close.iloc[i], d.atr.iloc[i])
        if not p:
            continue
        s = sim(d, i, p)
        if not s:
            continue
        buy, sell, k, why = s
        r = d.iloc[i]; dt = d.index[i]
        nn = n225[n225.index <= dt]
        c1 = lambda m: float(d.Close.iloc[min(i + m, len(d) - 1)]) / buy - 1
        pool.append({"date": dt, "code": code, "shares": p["shares"], "cost": p["entry"] * p["shares"],
                     "buy": buy, "sell": sell, "entry_date": d.index[i + 1], "exit_date": d.index[k], "why": why,
                     "pnl": (sell - buy) * p["shares"], "ret": sell / buy - 1,
                     "atrp": float(r.atr / r.Close), "ext": float(r.Close / r.sma25 - 1),
                     "r5": float(r.Close / d.Close.iloc[i - 5] - 1), "vr": float(r.Volume / r.vol20),
                     "gap": float(d.Open.iloc[i + 1] / r.Close - 1),
                     "mkt5": float(nn.iloc[-1] / nn.iloc[-6] - 1), "mkt_up": bool(nn.iloc[-1] > nn.tail(25).mean()),
                     "d1": c1(1), "d3": c1(3), "d5": c1(5)})
pool.sort(key=lambda t: (t["date"], -t["vr"]))
roff_ok = lambda t: not roff[at(t["date"])]
pool = [t for t in pool if roff_ok(t)]
print("シグナル", len(pool))


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
L = []
te = [t for t in pool if t["date"] >= SPLIT]
# A) 直近の4件の実際
L.append("## A. 直近の提案の実際の値動き")
for code in ("4493", "2914", "4704", "9104", "1321"):
    try:
        x = yf.download(f"{code}.T", start="2026-10-06", auto_adjust=False, progress=False)
        x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
        for dt, r in x.iterrows():
            L.append(f"{code} {dt.date()} 始{r.Open:.0f} 高{r.High:.0f} 安{r.Low:.0f} 終{r.Close:.0f} 出来高{r.Volume:,.0f}")
    except Exception as e:
        L.append(f"{code} 取得失敗 {e}")
for code in ("4493", "2914", "4704", "9104"):
    d = frames.get(code)
    if d is None: L.append(f"{code} 検証データ無し"); continue
    for dt in ("2026-10-09", "2026-10-13"):
        m = [k for k, x in enumerate(d.index) if str(x.date()) == dt]
        if m:
            r = d.iloc[m[0]]
            L.append(f"{code} {dt} 判定時：ATR/株価 {r.atr/r.Close*100:.1f}% 25日線乖離 {(r.Close/r.sma25-1)*100:.1f}% "
                     f"5日騰落 {(r.Close/d.Close.iloc[m[0]-5]-1)*100:.1f}% 売買代金20日 {r.turnover20/1e8:.0f}億 出来高倍率 {r.Volume/r.vol20:.2f}")
L.append(f"日経5日騰落（10/13）：{(n225.asof(pd.Timestamp('2026-10-13'))/n225[n225.index<=pd.Timestamp('2026-10-13')].iloc[-6]-1)*100:.1f}%")

# B) 想定内か：後半期間のシグナルの初動
L.append("\n## B. 検証（後半2024-01〜）で、買った後どれだけ下がるのが普通か")
import statistics as st
for k in ("d1", "d3", "d5"):
    v = [t[k] for t in te]
    L.append(f"{k[1]}日後：下落した割合 {sum(x<0 for x in v)/len(v)*100:.1f}% 中央値 {st.median(v)*100:+.2f}%  件数{len(v)}")
L.append(f"損切りで終わった割合 {sum(t['why']=='損切り' for t in te)/len(te)*100:.1f}% / 最終的に負け {sum(t['pnl']<=0 for t in te)/len(te)*100:.1f}%")
# 4件中3件以上が3日後マイナスになる確率（独立と仮定した二項）
p3 = sum(t["d3"] < 0 for t in te) / len(te)
from math import comb
pr = sum(comb(4, j) * p3**j * (1-p3)**(4-j) for j in (3, 4))
L.append(f"4件中3件以上が3日後にマイナスになる確率 = Σ C(4,j)·{p3:.3f}^j·{1-p3:.3f}^(4-j) (j=3,4) = {pr*100:.1f}%")
# 実際の最初の数件を同じ方法で並べた時の連敗
s = sorted(te, key=lambda t: t["date"]); worst = 0; cur = 0
for t in s:
    cur = cur + 1 if t["pnl"] <= 0 else 0; worst = max(worst, cur)
L.append(f"後半期間の最大連敗 {worst}回")

# C) 特徴ごとの勝ち負け（後半）
L.append("\n## C. 何が負けと関係していたか（後半・特徴の高低で2分）")
for f in ("atrp", "ext", "r5", "vr", "gap", "mkt5"):
    v = sorted(t[f] for t in te); med = v[len(v)//2]
    for name, g in (("低", [t for t in te if t[f] < med]), ("高", [t for t in te if t[f] >= med])):
        w = sum(t["pnl"] > 0 for t in g); gp = sum(t["pnl"] for t in g if t["pnl"] > 0); gl = -sum(t["pnl"] for t in g if t["pnl"] <= 0)
        L.append(f"{f} {name}（境 {med:.3f}）：件数{len(g)} 勝率{w/len(g)*100:.1f}% PF{gp/gl if gl else 0:.2f} 平均{st.mean(t['ret'] for t in g)*100:+.2f}%")
for name, g in (("日経25日線の上", [t for t in te if t["mkt_up"]]), ("日経25日線の下", [t for t in te if not t["mkt_up"]])):
    w = sum(t["pnl"] > 0 for t in g); gp = sum(t["pnl"] for t in g if t["pnl"] > 0); gl = -sum(t["pnl"] for t in g if t["pnl"] <= 0)
    L.append(f"{name}：件数{len(g)} 勝率{w/len(g)*100:.1f}% PF{gp/gl if gl else 0:.2f}")

# D) 後出しなし：前半で閾値を選び、後半で試す
L.append("\n## D. 改善候補（前半で選んだ条件を後半で試す。基準＝今の方式）")
base_tr, base_te = run(lambda t: True, start, SPLIT), run(lambda t: True, SPLIT, END)
L.append(f"今の方式：前半 日経比 {base_tr['vs']:+,} / 後半 日経比 {base_te['vs']:+,} 取引{base_te['n']} 勝{base_te['hit']} PF{base_te['pf']} 最大落ち込み{base_te['mdd']:,}")
cands = []
for th in (0.03, 0.035, 0.04, 0.05, 0.06):
    cands.append((f"ATR/株価 {th*100:.1f}%以下", lambda t, th=th: t["atrp"] <= th))
for th in (0.06, 0.08, 0.10, 0.12, 0.15):
    cands.append((f"25日線乖離 {th*100:.0f}%以下", lambda t, th=th: t["ext"] <= th))
for th in (0.05, 0.08, 0.10, 0.15):
    cands.append((f"5日騰落 {th*100:.0f}%以下", lambda t, th=th: t["r5"] <= th))
cands.append(("日経が25日線の上の時だけ", lambda t: t["mkt_up"]))
for th in (-0.03, -0.02, 0.0):
    cands.append((f"日経5日騰落 {th*100:.0f}%以上", lambda t, th=th: t["mkt5"] >= th))
res = []
for nm, fl in cands:
    a, b = run(fl, start, SPLIT), run(fl, SPLIT, END)
    res.append((nm, a, b))
res.sort(key=lambda x: -x[1]["vs"])
for nm, a, b in res:
    L.append(f"- {nm}：前半 {a['vs']-base_tr['vs']:+,}（基準比） → 後半 {b['vs']-base_te['vs']:+,}（基準比）  後半 取引{b['n']} 勝率{b['hit']/max(b['n'],1)*100:.1f}% PF{b['pf']} 最大落ち込み{b['mdd']:,}")
best = res[0]
L.append(f"\n前半で一番良かった：{best[0]} → 後半の基準比 {best[2]['vs']-base_te['vs']:+,} → {'予測出来た' if best[2]['vs'] > base_te['vs'] else '予測出来なかった'}")
open("data/compare7.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
