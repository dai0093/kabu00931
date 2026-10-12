"""市場リスクダッシュボードのデータ（HTML内の <script id="state"> またはそのJSON）から、
ロジックツリーの判定結果 data/logic_tree.json を作る。
フェーズ・閾値・枝はダッシュボード本体のスクリプト（RULE / layers / PH / renderDash）をそのまま移植し、
独自の閾値やフェーズは足さない（仕様書4章・13章）。
使い方: python3 scanner/logic_from_state.py <index.html または state.json>"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
src = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'<script id="state" type="application/json">\s*(\{.*?\})\s*</script>', src, re.S)
S = json.loads(m.group(1) if m else src)

ser = {s["id"]: s for s in S["series"]}
val = lambda k: ser[k]["value"] if k in ser and isinstance(ser[k].get("value"), (int, float)) else None
RULE = {
    "brent": lambda v: "lit" if v >= 110 else "near" if v >= 105 else "ok",
    "us10": lambda v: "lit" if v >= 5.00 else "near" if v >= 4.80 else "ok",
    "jgb10": lambda v: "lit" if v >= 3.00 else "near" if v >= 2.80 else "ok",
    "hy": lambda v: "lit" if v >= 3.00 else "near" if v >= 2.90 else "ok",
    "ig": lambda v: "lit" if v >= 0.95 else "near" if v >= 0.90 else "ok",
    "t10y2y": lambda v: "lit" if v < 0 else "near" if v < 0.10 else "ok",
    "nfci": lambda v: "lit" if v >= 0 else "near" if v >= -0.20 else "ok",
    "vix": lambda v: "lit" if (val("vixd") or 0) >= 3 else "near" if v >= 25 else "ok",
    "pcdef": lambda v: "lit" if v >= 6.0 else "near" if v >= 5.5 else "ok",
}
st = lambda k: "na" if val(k) is None or k not in RULE else RULE[k](val(k))
a, b = st("us10"), st("jgb10")
rate = "lit" if "lit" in (a, b) else "near" if "near" in (a, b) else "ok"
f = S["flags"]
L = {"origin": [["地政学", "lit" if f.get("geo") else "ok"], ["原油", st("brent")], ["日米金利", rate],
                ["AI債務", "lit" if f.get("ai") else "ok"],
                ["私募信用", "lit" if (f.get("gate") or st("pcdef") == "lit") else st("pcdef")]],
     "trans": [["HY OAS", st("hy")], ["IG OAS", st("ig")], ["AI→銀行", "near" if f.get("aibank") else "ok"],
               ["逆イールド", st("t10y2y")]],
     "fund": [["NFCI", st("nfci")], ["生保", "lit" if f.get("ins") else "ok"]],
     "market": [["VIX", st("vix")]]}
c = lambda k: sum(1 for x in L[k] if x[1] == "lit")
r, t, fu, mk = c("origin"), c("trans"), c("fund"), c("market")
ph = 0
if r: ph = 1
if t >= 1: ph = 2
if t >= 2: ph = 3
if fu: ph = 4
if fu and mk >= 2: ph = 5
PH = [["通常監視", "起点は点灯していません。"], ["起点発生", "信用への波及は未確認。原油・金利は別途監視。"],
      ["通り道の予兆", "信用層に1つ点灯。"], ["通り道が開通", "信用層に2つ以上点灯。"],
      ["資金調達ストレス", "強制売却の一段前。"], ["強制売却", "資金調達が詰まり市場も崩れています。"]]

# 鮮度（ダッシュボードと同じ：日次3日・週次9日・月次40日・四半期120日）
LIM = {"日次": 3, "週次": 9, "月次": 40, "四半期": 120}
today = datetime.now(JST).date()
stale = []
for s in S["series"]:
    try:
        age = (today - datetime.strptime(s["observedAt"], "%Y-%m-%d").date()).days
    except Exception:
        age = 9999
    if age > LIM.get(s.get("freq"), 30):
        stale.append({"name": s["name"], "observedAt": s.get("observedAt"), "freq": s.get("freq")})

out = {"updatedAt": S.get("updatedAt"), "builtAt": datetime.now(JST).isoformat(timespec="minutes"),
       "phase": ph, "phaseName": PH[ph][0], "phaseDesc": PH[ph][1],
       "counts": {"origin": [r, len(L["origin"])], "trans": [t, len(L["trans"])],
                  "fund": [fu, len(L["fund"])], "market": [mk, len(L["market"])]},
       "layers": L, "assets": S.get("assets", []),
       "values": {k: {"value": ser[k]["value"], "unit": ser[k].get("unit", ""), "observedAt": ser[k].get("observedAt"),
                      "change": ser[k].get("change", ""), "source": ser[k].get("source", "")}
                  for k in ("vix", "us10", "jgb10", "brent", "hy", "ig", "t10y2y", "nfci", "usdjpy") if k in ser},
       "stale": stale,
       "events": sorted(S.get("events", []), key=lambda e: e.get("date", ""), reverse=True)[:15],
       "source": "https://claude.ai/artifact/KJPgY7LSb8DMsdXt2A1Gst"}
json.dump(out, open("data/logic_tree.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"段階{ph}：{PH[ph][0]}  起点{r} 信用{t} 資金{fu} 市場{mk}  期限切れ{len(stale)}系列")
