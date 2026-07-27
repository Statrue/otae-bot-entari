"""诊断：FZ 快照 vs 森空岛 card/detail 的奖章关联匹配率。

读本地 snapshot + 最新 card_detail dump，不发网络请求。用于确认改用 name 关联后能匹配多少。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

snap = json.loads((ROOT / "data/endfield/medal_snapshot.json").read_text(encoding="utf-8"))
fz_names = [m["name"] for m in snap["current"]["medals"]]

dumps = sorted((ROOT / "data/_manual_test").glob("card_detail_raw_*.json"))
if not dumps:
    print("未找到 card_detail dump，请先用「手机登录」跑一次。")
    sys.exit(1)
raw = json.loads(dumps[-1].read_text(encoding="utf-8"))
sk_names = [m["achievementData"]["name"] for m in raw["data"]["detail"]["achieve"]["achieveMedals"]]


def norm(s: str) -> str:
    # 去所有空白 + 去首尾中英文引号
    return (
        "".join(str(s).split())
        .strip('"')
        .strip("'")
        .strip("“”‘’")
    )


for label, fn in [("原样", str), ("规范化", norm)]:
    fzset, skset = {fn(n) for n in fz_names}, {fn(n) for n in sk_names}
    print(f"[{label}] FZ={len(fzset)} 森空岛={len(skset)} 交集={len(fzset & skset)}")

fz_d = {norm(n): n for n in fz_names}
sk_d = {norm(n): n for n in sk_names}
fz_only = sorted(set(fz_d) - set(sk_d))
sk_only = sorted(set(sk_d) - set(fz_d))
print(f"\nFZ 有 / 森空岛无（{len(fz_only)}）:")
for k in fz_only:
    print(f"  {fz_d[k]}")
print(f"\n森空岛有 / FZ 无（{len(sk_only)}）:")
for k in sk_only:
    print(f"  {sk_d[k]}")
