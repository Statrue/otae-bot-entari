"""诊断2：调度券 level + 未匹配项详情。读本地文件，不发请求。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def norm(s: str) -> str:
    return "".join(str(s).split()).strip('"').strip("'").strip("“”‘’")


snap = json.loads((ROOT / "data/endfield/medal_snapshot.json").read_text(encoding="utf-8"))
fz = snap["current"]["medals"]
dumps = sorted((ROOT / "data/_manual_test").glob("card_detail_raw_*.json"))
raw = json.loads(dumps[-1].read_text(encoding="utf-8"))
sk = raw["data"]["detail"]["achieve"]["achieveMedals"]

print("=== 森空岛 调度券系列（level / isPlated / initLevel / name）===")
for m in sk:
    n = m["achievementData"]["name"]
    if "调度" in n:
        a = m["achievementData"]
        print(f"  level={m.get('level')} isPlated={m.get('isPlated')} initLevel={a.get('initLevel')} cate={a.get('cate')} | {n}")

print("\n=== FZ 有 / 森空岛无（规范化 name 未匹配，即被判未获得）===")
sk_names = {norm(m["achievementData"]["name"]) for m in sk}
for m in fz:
    if norm(m["name"]) not in sk_names:
        print(f"  id={m['medal_id']} max={m['max_level']} up={m['can_be_upgraded']} plate={m['can_be_plated']} | {m['name']}")
