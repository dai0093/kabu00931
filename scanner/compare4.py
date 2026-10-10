"""検証4：市場リスクとの連携は成績を良くするか（高値更新・売買代金100億円以上・待機資金は日経）
A 連携なし（現行）
B リスクオフ中は新規の買いを止める
C リスクオフ中は株数を半分にする
D 急変している要因（原油・米金利・円高）に弱い銘柄は買わない（60日の感応度で判定）
E B＋リスクオフに入ったら保有株を翌朝売り、待機資金も日経から現金へ退避
F D＋B"""
import json
import numpy as np
import pandas as pd
from core import plan, add_indicators, CAPITAL, MAX_POSITIONS
from data import load
import strategy
from strategy import is_breakout, simulate_trend
import risk as R
from risk import factors, risk_off, state

strategy.MIN_TURNOVER = 100e8
U = json.load(open("data/universe_all.json", encoding="utf-8"))
raw = load("5y", codes=list(U), size=50, wait=10)
frames = {}
for c, df in raw.items():
    df = df.copy(); df.index = pd.to_datetime(df.index).tz_localize(None)
    frames[c] = add_indicators(df)
F = factors("6y")
import risk as R
print("銘柄", len(frames), "指標", F.index[0].date(), "〜", F.index[-1].date(),
      "HY開始", F["hy"].first_valid_index())
roff = {d: risk_off(F.loc[d]) for d in F.index}
st = {d: state(F.loc[d]) for d in F.index}


def at(d):
    k = F.index.searchsorted(d, side="right") - 1
    return F.index[max(k, 0)]


def sens(d, i):
    """60日の日次リターン相関：原油・米金利変化・ドル円"""
    if i < 61:
        return {}
    r = d.Close.pct_change().iloc[i - 59:i + 1]
    ff = F.reindex(r.index, method="ffill")
    out = {}
    for k, x in (("oil", ff.brent.pct_change()), ("rate", ff.us10.diff()), ("yen", ff.usdjpy.pct_change())):
        a = pd.concat([r, x], axis=1).dropna()
        out[k] = float(a.corr().iloc[0, 1]) if len(a) > 30 else 0.0
    return out


def vulnerable(d, i):
    """今急変している要因に対して、逆方向に動きやすい銘柄か"""
    s = st[at(d.index[i])]
    se = sens(d, i)
    if not se:
        return False
    if s["oil_jump"] in ("lit", "near") and se["oil"] < -0.3:
        return True
    if s["us10_jump"] in ("lit", "near") and se["rate"] < -0.3:
        return True
    if s["yen_jump"] in ("lit", "near") and se["yen"] > 0.3:
        return True
    return False


# 全シグナル（共通）
base = []
for code, d in frames.items():
    for i in range(86, len(d)):
        if is_breakout(d, i):
            base.append((code, i))
print("シグナル", len(base))
vul = {(c, i): vulnerable(frames[c], i) for c, i in base}
print("感応度で除外対象", sum(vul.values()))


def run(name, block=False, half=False, avoid=False, exit_all=False):
    cands = []
    for code, i in base:
        d = frames[code]; dt = at(d.index[i])
        if block and roff[dt]:
            continue
        if avoid and vul[(code, i)]:
            continue
        p = plan(d.Close.iloc[i], d.atr.iloc[i])
        if not p:
            continue
        if half and roff[dt]:
            p = dict(p, shares=max(0, (p["shares"] // 200) * 100)); p["cost"] = p["entry"] * p["shares"]
            if not p["shares"]:
                continue
        r = simulate_trend(d, i, p)
        if r["status"] != "closed":
            continue
        t = {"date": str(d.index[i].date()), "code": code,
             "vr": float(d.Volume.iloc[i] / d.vol20.iloc[i]), **p, **r}
        if exit_all:   # 保有中にリスクオフ入りしたら、翌営業日の寄りで売る
            k0 = i + 1
            ex = d.index.get_loc(pd.Timestamp(t["exit_date"]))
            for k in range(k0, ex):
                if roff[at(d.index[k])] and not roff[at(d.index[k - 1])] and k + 1 <= ex:
                    px = float(d.Open.iloc[k + 1])
                    t.update(sell=px, exit_date=str(d.index[k + 1].date()), reason="リスクオフ",
                             pnl=(px - t["buy"]) * t["shares"], hit=px > t["buy"])
                    break
        cands.append(t)
    cands.sort(key=lambda t: (t["date"], -t["vr"]))
    open_pos, trades = [], []
    for t in cands:
        open_pos = [o for o in open_pos if o["exit_date"] > t["date"]]
        used = sum(o["buy"] * o["shares"] for o in open_pos)
        if (len(open_pos) >= MAX_POSITIONS or used + t["cost"] > CAPITAL
                or any(o["code"] == t["code"] for o in open_pos)):
            continue
        open_pos.append(t); trades.append(t)
    # 資産推移
    n = F["n225"]; n = n[n.index >= min(d.index[0] for d in frames.values())]
    ret = n.pct_change().fillna(0)
    buys, sells = {}, {}
    for t in trades:
        buys.setdefault(t["entry_date"], []).append(t); sells.setdefault(t["exit_date"], []).append(t)
    idle, held, eq = float(CAPITAL), [], []
    for dt, r in ret.items():
        ds = str(dt.date())
        park = not (exit_all and roff[at(dt - pd.Timedelta(days=1))])
        if park:
            idle *= 1 + float(r)
        for t in buys.get(ds, []):
            idle -= t["buy"] * t["shares"]; held.append(t)
        for t in sells.get(ds, []):
            idle += t["sell"] * t["shares"]; held = [h for h in held if h is not t]
        val = sum(float(frames[h["code"]].Close.asof(dt)) * h["shares"] for h in held)
        eq.append(idle + val)
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v); mdd = min(mdd, v - peak)
    wins = [t for t in trades if t["hit"]]
    gp = sum(t["pnl"] for t in wins); gl = -sum(t["pnl"] for t in trades if not t["hit"])
    yrs = {}
    for t in trades:
        yrs[t["date"][:4]] = yrs.get(t["date"][:4], 0) + t["pnl"]
    bench = CAPITAL * (float(n.iloc[-1]) / float(n.iloc[0]) - 1)
    return {"name": name, "n": len(trades), "hit": len(wins), "miss": len(trades) - len(wins),
            "gp": round(gp), "gl": round(gl), "pf": round(gp / gl, 2) if gl else None,
            "profit": round(eq[-1] - CAPITAL), "vs_nikkei": round(eq[-1] - CAPITAL - bench),
            "mdd": round(mdd), "bench": round(bench),
            "years": {y: round(v) for y, v in sorted(yrs.items())}}


res, spans_all = [], {}
for th in (0.0, 0.02, 0.03, 0.04):
    R.CREDIT_TH = th
    roff = {d: risk_off(F.loc[d]) for d in F.index}
    name = "B VIXのみ" if th == 0 else f"B VIX＋信用（HYG/IEFが20日で−{th*100:.0f}%）"
    r = run(name, block=True); r["roff_days"] = sum(roff.values()); res.append(r)
    sp, on = [], None
    for d in F.index:
        if roff[d] and on is None: on = d
        if not roff[d] and on is not None: sp.append(f"{on.date()}〜{d.date()}"); on = None
    spans_all[name] = sp
R.CREDIT_TH = 0.0
roff = {d: False for d in F.index}
res.insert(0, run("A 連携なし"))
json.dump({"results": res, "spans": spans_all}, open("data/compare5.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lines = [f"日経平均保有 {res[0]['bench']:+,}円", f"HYG/IEFの20日変化 最小 {F.credit_20.min()*100:.1f}%", ""]
for r in res:
    lines.append(f"## {r['name']}（リスクオフ {r.get('roff_days',0)}日）\n- 最終利益 {r['profit']:+,} / 日経比 {r['vs_nikkei']:+,} / 最大落ち込み {r['mdd']:,}"
                 f"\n- 取引{r['n']} 出来た{r['hit']} 出来なかった{r['miss']} PF{r['pf']}\n- 年別 {r['years']}\n")
for k, v in spans_all.items():
    lines.append(f"{k} の期間: {v}")
open("data/compare5.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
