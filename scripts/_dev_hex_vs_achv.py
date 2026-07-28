"""临时调研：把刚抓到的森空岛 card/detail 的 hex id 与 FZ 快照 achv_ id 按 name 并排对照。"""
from __future__ import annotations

import glob
import json

from plugins.endfield.service import _norm_medal_name


def main() -> None:
    dumps = sorted(glob.glob("data/_manual_test/card_detail_raw_*.json"))
    raw = json.load(open(dumps[-1], encoding="utf-8"))
    medals = raw["data"]["detail"]["achieve"]["achieveMedals"]
    sk: dict[str, tuple] = {}
    for m in medals:
        ad = m.get("achievementData") or {}
        nm = ad.get("name")
        if nm:
            sk[_norm_medal_name(nm)] = (ad.get("id"), nm, m.get("level"), m.get("isPlated"))
    print(f"Skland achieveMedals: {len(medals)} 枚（规范化 name 去重后 {len(sk)}）")
    sample_ids = [v[0] for v in list(sk.values())[:3]]
    print("Skland id 样例:", sample_ids)
    print("Skland id 长度集合:", sorted({len(v[0]) for v in sk.values() if v[0]}))
    print("是否有任何 Skland id 以 achv_ 开头?:", any((v[0] or "").startswith("achv_") for v in sk.values()))
    any_match = any((v[0] or "") in {fz for fz in []} for v in sk.values())
    print()

    snap = json.load(open("data/endfield/medal_snapshot.json", encoding="utf-8"))
    fz: dict[str, str] = {}
    for m in (snap.get("current") or {}).get("medals", []):
        if m.get("name"):
            fz[_norm_medal_name(m["name"])] = m.get("medal_id")
    fz_id_set = {v for v in fz.values() if v}
    print(f"FZ snapshot: {len(snap.get('medals', []))} 枚")
    print("FZ id 是否有任何与 Skland hex 相等?:",
          any((v[0] or "") in fz_id_set for v in sk.values()))
    print()

    print("=== 武陵调度系列：Skland hex vs FZ achv_ ===")
    for _key, (hid, nm, lv, plated) in sorted(sk.items()):
        if "武陵调度" in nm:
            fzid = fz.get(_norm_medal_name(nm), "<FZ 快照无此名>")
            print(f"  {nm:<14} lv={lv} plated={plated}  Skland={hid}  FZ={fzid}")
    print()

    print("=== 普通章抽样：Skland hex vs FZ achv_（同 name）===")
    n = 0
    for _key, (hid, nm, _lv, _plated) in sorted(sk.items()):
        if "武陵" in nm:
            continue
        fzid = fz.get(_key, "<FZ 快照无此名>")
        print(f"  {nm:<16} Skland={hid:<34} FZ={fzid}")
        n += 1
        if n >= 8:
            break


if __name__ == "__main__":
    main()
