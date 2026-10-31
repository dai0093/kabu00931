"""データの健全性チェック：判定に使うデータが欠けていたり古いと、指摘される前に通知し、画面最上部に出す（data/health.json）。"""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone, date
JST = timezone(timedelta(hours=9)); now = datetime.now(JST); P = []
def ld(f):
    try: return json.load(open(f, encoding="utf-8"))
    except Exception: return None
def bd(d0):  # 平日ベースの経過営業日数（祝日は考慮しない）
    d = datetime.strptime(d0, "%Y-%m-%d").date(); t = now.date(); n = 0
    while d < t:
        d += timedelta(days=1); n += d.weekday() < 5
    return n
D = ld("data/defense.json")
if not D: P.append("防御判定（defense.json）が読めない")
else:
    lag = bd(D["asOf"]) - (0 if now.hour >= 16 else 1)
    if lag >= 1: P.append(f"防御判定の日付が古い（{D['asOf']}）")
    if "前回の判定を維持" in (D.get("note") or ""): P.append("日経データ欠損で前回の判定を維持中")
    sx = list((D.get("dbg_sox") or {}).keys())
    if sx and bd(sx[-1]) - (0 if now.hour >= 7 else 1) >= 2: P.append(f"SOXが古い（{sx[-1]}）")
F = ld("data/finwatch.json")
if F:
    if F.get("missing"): P.append("金融機関の取得失敗：" + "、".join(F["missing"]))
    if F.get("stale"): P.append(f"金融機関の未更新 {len(F['stale'])}銘柄")
    c = F.get("credit") or {}
    if c.get("error") or not c: P.append("信用（社債ETF）が取れていない")
    try:
        if (now - datetime.fromisoformat(F["updatedAt"])).total_seconds() > 36 * 3600: P.append(f"金融機関の更新が止まっている（{F['updatedAt']}）")
    except Exception: pass
T = ld("data/logic_tree.json")
if T:
    if T.get("held"): P.append("ロジックツリーで古い値のまま点灯保持：" + "、".join(T["held"]))
    if T.get("unjudged"): P.append("ロジックツリーで判定不能：" + "、".join(T["unjudged"]))
S = ld("data/series_live.json") or {}
for k, n in (("hy", "HY OAS"), ("ig", "IG OAS"), ("nfci", "NFCI")):
    if k not in S: P.append(f"{n}は自動取得できていない（社債ETFで代用中）")
H = {"at": now.isoformat(timespec="minutes"), "ok": not P, "problems": P}
old = ld("data/health.json") or {}
json.dump(H, open("data/health.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 新しい問題が増えた時だけ通知（同じ内容を何度も送らない）
new = [p for p in P if p not in (old.get("problems") or [])]
T_ = os.environ.get("NTFY_TOPIC")
if T_ and new:
    q = urllib.parse.urlencode({"title": "【データ欠損】判定が不完全です", "priority": "4", "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{T_}?{q}", data="\n".join(new).encode("utf-8"), method="POST"), timeout=30)
print(H)
