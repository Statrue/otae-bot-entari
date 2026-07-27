"""验证 build_medal_missing_view：suspect、三段详情、潜能奖章状态。读本地 dump+snapshot。"""
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
from plugins.endfield.service import EndfieldService, _norm_medal_name, _parse_player_medal_progress

store = MedalSnapshotStore()
snap = store.load_current_view()
dumps = sorted((ROOT / "data/_manual_test").glob("card_detail_raw_*.json"))
raw = json.loads(dumps[-1].read_text(encoding="utf-8"))
svc = EndfieldService(WarfarinClient())
view = svc.build_medal_missing_view(raw, snap, nickname="x", uid="y", server_name="z")
progress = _parse_player_medal_progress(raw)

print(f"level_counts: {dict(sorted(view.level_counts.items()))}")
print(f"suspect_names ({len(view.suspect_names)}): {view.suspect_names}")

print("\n=== 未获得 ===")
for m in view.not_obtained:
    tag = "[SUSPECT]" if m.name in view.suspect_names else "         "
    print(f"  {tag} {m.name} | max={m.max_level} up={m.can_be_upgraded} plate={m.can_be_plated}")

print("\n=== 未升满 ===")
for m in view.not_maxed:
    print(f"  {m.name} | max={m.max_level} up={m.can_be_upgraded}")

print("\n=== 未镀层 ===")
for m in view.not_plated:
    print(f"  {m.name} | plate={m.can_be_plated}")

print("\n=== 含「潜能」的奖章（FZ 视角 + 森空岛进度）===")
for m in snap.medals:
    if "潜能" in m.name:
        info = progress.get(_norm_medal_name(m.name))
        st = "无进度(未获得)" if info is None else f"lv={info.level} plated={info.plated}"
        print(f"  {m.name} | max={m.max_level} up={m.can_be_upgraded} plate={m.can_be_plated} | 森空岛:{st}")
