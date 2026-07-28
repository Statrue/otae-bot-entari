"""验证 build_medal_missing_view：三段详情 + 潜能奖章状态（md5-id 关联）。读本地 dump+snapshot。"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from plugins.endfield.client import WarfarinClient
from plugins.endfield.medal_store import MedalSnapshotStore
from plugins.endfield.service import EndfieldService, _parse_player_medal_progress

store = MedalSnapshotStore()
snap = store.load_current_view()
dumps = sorted((ROOT / "data/_manual_test").glob("card_detail_raw_*.json"))
raw = json.loads(dumps[-1].read_text(encoding="utf-8"))
svc = EndfieldService(WarfarinClient())
view = svc.build_medal_missing_view(raw, snap, nickname="x", uid="y", server_name="z")
progress_by_hex, _progress_by_name = _parse_player_medal_progress(raw)

print(f"level_counts: {dict(sorted(view.level_counts.items()))}")
print(f"owned {view.owned_count}/{view.total_count} · 未获得 {len(view.not_obtained)} · 未升满 {len(view.not_maxed)} · 未镀层 {len(view.not_plated)}")

print("\n=== 未获得 ===")
for m in view.not_obtained:
    print(f"  {m.name} | max={m.max_level} up={m.can_be_upgraded} plate={m.can_be_plated}")

print("\n=== 未升满 ===")
for m in view.not_maxed:
    print(f"  {m.name} | max={m.max_level} up={m.can_be_upgraded}")

print("\n=== 未镀层 ===")
for m in view.not_plated:
    print(f"  {m.name} | plate={m.can_be_plated}")

print("\n=== 含「潜能」的奖章（FZ 视角 + 森空岛进度，按 md5-id）===")
for m in snap.medals:
    if "潜能" in m.name:
        info = progress_by_hex.get(hashlib.md5((m.medal_id or "").encode()).hexdigest())
        st = "无进度(未获得)" if info is None else f"lv={info.level} plated={info.plated}"
        print(f"  {m.name} | max={m.max_level} up={m.can_be_upgraded} plate={m.can_be_plated} | 森空岛:{st}")
