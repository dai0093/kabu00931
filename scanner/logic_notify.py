"""ロジックツリー通知：data/logic_tree.json（市場リスクダッシュボードの定時更新が書き込む）を
前回版と比べ、重要な状態変化だけをntfyへ送る。仕様書10章：
- 通知する：フェーズ変化、枝の状態変化（点灯／接近／未点灯）、新しい事象（実行済み・接近・緩和・訂正）
- 通知しない：既知情報の再掲、価格更新だけ
- 同じ事象・同じ状態は重複させない（事象は 日付|見出し|状態 で識別）"""
import json
import os
import subprocess
import urllib.parse
import urllib.request

TOPIC = os.environ.get("NTFY_TOPIC", "")
LINK = "https://dai0093.github.io/kabu00931/signals.html#logic"
LAB = {"lit": "点灯", "near": "接近", "ok": "未点灯", "na": "未取得", "stale": "期限切れ"}

cur = json.load(open("data/logic_tree.json", encoding="utf-8"))
try:
    prev = json.loads(subprocess.run(["git", "show", "HEAD~1:data/logic_tree.json"],
                                     capture_output=True, text=True, check=True).stdout)
except Exception:
    prev = {}

lines = []
if prev.get("phase") != cur.get("phase"):
    lines.append(f"フェーズ {prev.get('phase', '—')} → {cur['phase']}：{cur.get('phaseName', '')}")

def states(d):
    return {f"{ly}:{n}": s for ly, items in (d.get("layers") or {}).items() for n, s in items}
p, c = states(prev), states(cur)
for k, s in c.items():
    if p.get(k) != s and s != "na":
        lines.append(f"{k.split(':')[1]}：{LAB.get(p.get(k), '—')} → {LAB.get(s, s)}")

key = lambda e: f"{e.get('date')}|{e.get('title')}|{e.get('state')}"
seen = {key(e) for e in prev.get("events", [])}
new_ev = [e for e in cur.get("events", []) if key(e) not in seen
          and e.get("state") in ("実行済み", "接近", "緩和", "訂正")]
for e in new_ev[:4]:
    lines.append(f"【{e['state']}】{e['date']} {e['title']}\n影響：{e.get('impact', '')[:80]}\n出典：{e.get('source', '')}")

log = {"checked": cur.get("updatedAt"), "sent": False, "items": len(lines)}
if lines and TOPIC:
    title = f"ロジックツリー：段階{cur['phase']} {cur.get('phaseName', '')}"
    body = "\n\n".join(lines[:8])
    q = urllib.parse.urlencode({"title": title, "click": LINK})
    for k in range(3):
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}",
                                   data=body.encode("utf-8"), method="POST"), timeout=30)
            log["sent"] = True; break
        except Exception as e:
            log["error"] = str(e)
    print(title); print(body)
else:
    print("通知なし（重要な変化なし）")
json.dump(log, open("data/logic_notify_log.json", "w", encoding="utf-8"), ensure_ascii=False)
