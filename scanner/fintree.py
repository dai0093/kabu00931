"""金融機関株価 → ロジックツリーの枝「金融機関株価」。判定基準は検証16（data/compare16.md）から作成。
目的変数＝10営業日以内に日経が-7%以下。群の中央値が下の条件を超えたら:
  点灯（平均の約3倍の発生率、前後半とも）: 欧州銀 5日≤-15% / 米銀 前日≤-5% / 米銀 5日≤-10% / 邦銀 5日≤-10%
  接近（約2倍）: 私募信用 5日≤-8% / 欧州銀 前日≤-3% / 欧州銀 5日≤-8% / 米銀 5日≤-5% / 邦銀 5日≤-6%
点灯＝点灯条件が1つ以上。接近＝接近条件が1つ以上。"""
LIT = [("欧州銀", "med_d5", -15), ("米銀", "med_d1", -5), ("米銀", "med_d5", -10), ("日本", "med_d5", -10)]
NEAR = [("私募信用", "med_d5", -8), ("欧州銀", "med_d1", -3), ("欧州銀", "med_d5", -8), ("米銀", "med_d5", -5), ("日本", "med_d5", -6)]
GN = {"PC": "私募信用"}
def state(groups):
    g = {GN.get(k, k): v for k, v in groups.items()}
    hit = lambda L: [f"{n}{'前日' if m=='med_d1' else '5日'}{g[n][m]}%≤{t}%" for n, m, t in L if n in g and g[n][m] <= t]
    lit, near = hit(LIT), hit(NEAR)
    return ("lit" if lit else "near" if near else "ok"), lit or near
def apply(tree, st):
    """logic_tree.json の信用層に枝を入れ、段階を再計算（ロジックは logic_from_state.py と同じ）"""
    tr = [x for x in tree["layers"]["trans"] if x[0] != "金融機関株価"]
    tr.append(["金融機関株価", st]); tree["layers"]["trans"] = tr
    c = lambda k: sum(1 for x in tree["layers"][k] if x[1] == "lit")
    r, t, fu, mk = c("origin"), c("trans"), c("fund"), c("market")
    ph = 0
    if r: ph = 1
    if t >= 1: ph = 2
    if t >= 2: ph = 3
    if fu: ph = 4
    if fu and mk >= 2: ph = 5
    tree["phase"] = ph
    tree["counts"] = {k: [c(k), len(tree["layers"][k])] for k in ("origin", "trans", "fund", "market")}
    return tree
