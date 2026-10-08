"""保有11銘柄に「25日線ルール」を過去5年当てはめた検証。
ルール：終値が25日線を割ったら翌日寄りで売り、上に戻ったら翌日寄りで買い直す。
比較：5年間ずっと持ち続けた場合。
判定：売り指示のあと20営業日後の終値が売値より安ければ「予測出来た」。"""
import json
import yfinance as yf
from holdings import HELD

out, lines = {}, []
raw = yf.download([f"{c}.T" for c in HELD], period="5y", group_by="ticker",
                  auto_adjust=True, progress=False)
for c, name in HELD.items():
    try:
        d = raw[f"{c}.T"].dropna(subset=["Close"]).copy()
    except Exception:
        continue
    d["sma25"] = d.Close.rolling(25).mean()
    # データ異常チェック：1日で±40%以上の変化（分割の反映漏れなど）
    jumps = [(str(i.date()), round(float(r), 3)) for i, r in d.Close.pct_change().items()
             if abs(r) > 0.4]
    d = d.dropna(subset=["sma25"])
    n = len(d)
    hold_ret = float(d.Close.iloc[-1] / d.Open.iloc[1] - 1)

    # ルール運用
    eq, inpos, buy_px = 1.0, True, float(d.Open.iloc[1])
    curve, sells, hits, misses = [], 0, 0, 0
    for k in range(1, n - 1):
        r, nx = d.iloc[k], d.iloc[k + 1]
        if inpos and r.Close < r.sma25:
            sell_px = float(nx.Open)
            eq *= sell_px / buy_px
            inpos, sells = False, sells + 1
            if k + 21 < n:   # 20営業日後と比較
                later = float(d.Close.iloc[k + 21])
                if later < sell_px:
                    hits += 1
                else:
                    misses += 1
        elif not inpos and r.Close > r.sma25:
            buy_px, inpos = float(nx.Open), True
        curve.append(eq * (float(r.Close) / buy_px if inpos else 1))
    if inpos:
        eq *= float(d.Close.iloc[-1]) / buy_px
    rule_ret = eq - 1

    def mdd(series):
        peak, m = series[0], 0.0
        for v in series:
            peak = max(peak, v); m = min(m, v / peak - 1)
        return m
    hold_curve = list(d.Close / d.Open.iloc[1])
    res = {"name": name, "hold_pct": round(hold_ret * 100, 1), "rule_pct": round(rule_ret * 100, 1),
           "hold_mdd": round(mdd(hold_curve) * 100, 1), "rule_mdd": round(mdd(curve) * 100, 1),
           "sells": sells, "hit": hits, "miss": misses,
           "last_close": round(float(d.Close.iloc[-1]), 1),
           "last5": [round(float(x), 1) for x in d.Close.tail(5)], "jumps": jumps,
           "start": str(d.index[1].date())}
    out[c] = res
    lines.append(f"{c} {name}: 持ち続け{res['hold_pct']}%(最大DD{res['hold_mdd']}%) / "
                 f"ルール{res['rule_pct']}%(最大DD{res['rule_mdd']}%) / 売り{sells}回 "
                 f"出来た{hits} 出来なかった{misses} / 直近{res['last5']} / 急変{jumps}")
json.dump(out, open("data/held_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open("data/held_check.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
