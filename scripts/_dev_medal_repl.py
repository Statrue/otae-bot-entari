"""命令行手动测试工具：模拟 bot 的奖章命令处理，结果图片存本地并自动预览。

不依赖 QQ 协议端、不需要 .env。复用 bot 真实的 ``parse_command`` 解析 +
``EndfieldService`` / ``draw`` / ``EndfieldOfficialClient`` 处理。

支持命令（可带或不带 /zmd 前缀）：
  奖章                 读快照出统计图（秒回，需先「奖章 刷新」建快照）
  奖章 刷新            重新抓取 AKEData 全量数据 + 上一版本基线（源和源对比）
  奖章 缺章 [token]    个人缺章图；交互模式可选 手机号验证码 登录
  发码 <手机号>         发送森空岛登录验证码（手机号方式第一步）
  手机登录 <手机号> <验证码>  验证码换 token、缓存 token、查缺章（第二步）
  重查                 用已缓存的 token 重新查缺章（调试用，无需再发码）

诊断：手机登录/重查 会把 card/detail 原始响应 dump 到 data/_manual_test/ 并打印
achieve 路径结构，便于排查 achieveMedals 解析。token 缓存在
data/_manual_test/.token_cache（仅本机，可用「清缓存」删除）。

用法：
  交互模式：.venv\\Scripts\\python.exe scripts\\_dev_medal_repl.py
  单次模式：.venv\\Scripts\\python.exe scripts\\_dev_medal_repl.py 奖章
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUT = ROOT / "data" / "_manual_test"
OUT.mkdir(parents=True, exist_ok=True)
TOKEN_CACHE = OUT / ".token_cache"

from plugins.endfield.account_client import EndfieldAPIError, EndfieldOfficialClient
from plugins.endfield.client import WarfarinClient
from plugins.endfield.commands import parse_command
from plugins.endfield.draw import draw_medal_missing_card, draw_medal_stats_card
from plugins.endfield.medal_store import MedalSnapshotStore
from plugins.endfield.service import EndfieldService
from utils.http_client import close_http_client
from utils.image_utils import close_browser

client = WarfarinClient(timeout=30.0)
service = EndfieldService(client)
official = EndfieldOfficialClient()
store = MedalSnapshotStore()


def _mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else phone


def _load_cached_token() -> str:
    try:
        return TOKEN_CACHE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _save_cached_token(token: str) -> None:
    try:
        TOKEN_CACHE.write_text(token, encoding="utf-8")
    except Exception:
        pass


def _dump_card_detail(raw: dict) -> None:
    """诊断：dump card/detail 原始响应 + 打印 achieve 路径结构。"""
    stamp = int(time.time())
    dump_path = OUT / f"card_detail_raw_{stamp}.json"
    try:
        dump_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [诊断] 完整响应已保存: {dump_path}")
    except Exception as exc:
        print(f"  [诊断] dump 失败: {exc}")

    data = raw.get("data") if isinstance(raw, dict) else None
    print(f"  [诊断] raw.data 类型: {type(data).__name__}")
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        print(f"  [诊断] data.detail keys: {list(detail.keys())}")
        achieve = detail.get("achieve")
        if isinstance(achieve, dict):
            print(f"  [诊断] achieve keys: {list(achieve.keys())}")
            medals = achieve.get("achieveMedals")
            n = len(medals) if isinstance(medals, list) else "N/A"
            print(f"  [诊断] achieveMedals: 类型={type(medals).__name__} 数量={n}")
            if isinstance(medals, list) and medals and isinstance(medals[0], dict):
                print(f"  [诊断] achieveMedals[0] keys: {list(medals[0].keys())}")
        else:
            print(f"  [诊断] detail.achieve 缺失或非 dict: {type(achieve).__name__}")
    else:
        print("  [诊断] data.detail 缺失或非 dict")

    found: list[tuple[str, str, object]] = []

    def _find(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k).lower()
                if "medal" in key or "achieve" in key:
                    size = len(v) if isinstance(v, (list, dict)) else v
                    found.append((f"{path}.{k}", type(v).__name__, size))
                _find(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:3]):
                _find(v, f"{path}[{i}]")

    _find(raw)
    if found:
        print("  [诊断] 递归找到的 achieve/medal 相关字段:")
        for p, t, n in found[:25]:
            print(f"    {p}  ({t}, {n})")


def _save_and_open(pngs: tuple[bytes, ...], prefix: str) -> list[Path]:
    stamp = int(time.time())
    paths = [OUT / f"{prefix}_{stamp}_{i}.png" for i in range(1, len(pngs) + 1)]
    for path, png in zip(paths, pngs):
        path.write_bytes(png)
        print(f"  图片已保存: {path}")
    if paths and os.name == "nt":
        try:
            os.startfile(str(paths[0]))
        except Exception:
            pass
    return paths


async def cmd_medal_view() -> None:
    current = store.load_current_view()
    if current is None:
        print("  暂无快照，请先执行：奖章 刷新")
        return
    baseline = store.load_baseline_view()
    diff = service.build_medal_diff(current, baseline)
    prev_tag = f"相较 {baseline.version} " if baseline else ""
    print(
        f"  总数 {current.total_count} · 等级 {dict(sorted(current.level_counts.items()))}"
        f" · 可镀层 {current.platable_count} · 可升级 {current.upgradable_count}"
        f" · {prev_tag}本版本新增 {len(diff.new_medals)} · 版本 {current.version}"
    )
    pngs = await draw_medal_stats_card(diff)
    _save_and_open(pngs, "medal_view")


async def cmd_medal_refresh() -> None:
    print("  正在抓取 AKEData 蚀刻章全量数据…")
    started = time.perf_counter()
    snapshot = await service.fetch_medal_snapshot_akedata()
    await store.replace_current(snapshot)
    baseline = await service.fetch_akedata_baseline()
    await store.replace_baseline(baseline)
    bl = f"{baseline.version}({len(baseline.ids)} ids)" if baseline else "无更早版本"
    print(f"  已抓取 {snapshot.total_count} 枚 · 基线 {bl} · 耗时 {time.perf_counter() - started:.1f}s")
    await cmd_medal_view()


async def _medal_missing_with_token(token: str, *, interactive: bool) -> None:
    current = store.load_current_view()
    if current is None:
        print("  暂无快照，请先执行：奖章 刷新")
        return
    print("  正在查询森空岛账号角色…")
    roles = await official.discover_roles(token)
    if not roles:
        print("  该账号下未找到终末地角色（token 可能已失效）")
        return
    role = roles[0]
    if len(roles) > 1:
        print("  检测到多个角色：")
        for i, r in enumerate(roles, 1):
            print(f"    {i}. {r.nickname} · {r.server_name or r.server_id} · UID {r.role_id}")
        if interactive:
            choice = input("  选择编号（回车默认 1）：").strip()
            idx = (int(choice) - 1) if choice.isdigit() and 1 <= int(choice) <= len(roles) else 0
            role = roles[idx]
        else:
            print(f"  单次模式默认使用第一个：{role.nickname}")
    print(f"  正在查询 {role.nickname} 的奖章进度…")
    raw = await official.endfield_card_detail(token, role)
    _dump_card_detail(raw)
    view = service.build_medal_missing_view(
        raw, current,
        nickname=role.nickname,
        uid=f"***{str(role.role_id)[-4:]}",
        server_name=role.server_name or role.server_id,
    )
    print(
        f"  未获得 {len(view.not_obtained)} · 未升满 {len(view.not_maxed)} · 未镀层 {len(view.not_plated)}"
        f" · 已获得 {view.owned_count}/{view.total_count} · 截断 {view.truncated}"
    )
    pngs = await draw_medal_missing_card(view)
    _save_and_open(pngs, "medal_missing")


async def cmd_send_code(phone: str) -> bool:
    if not (phone.isdigit() and len(phone) == 11):
        print("  手机号格式不正确（应为 11 位数字）")
        return False
    print(f"  正在向 {_mask_phone(phone)} 发送森空岛登录验证码…")
    await official.send_phone_code(phone)
    print("  验证码已发送，请查收短信。")
    return True


async def cmd_medal_missing_by_phone(phone: str, code: str, *, interactive: bool) -> None:
    print("  正在用手机号 + 验证码换取账号 token…")
    token = await official.token_by_phone_code(phone, code)
    _save_cached_token(token)
    print("  token 已换取并缓存（供「重查」复用，无需再发码）")
    await _medal_missing_with_token(token, interactive=interactive)


async def dispatch(text: str, *, interactive: bool) -> None:
    text = text.strip()
    for prefix in ("/zmd", "/终末地", "/ef", "zmd", "终末地", "endfield", "ef"):
        if text == prefix or text.startswith(prefix + " "):
            text = text[len(prefix):].strip()
            break
    if not text:
        return
    parts = text.split()
    head = parts[0]

    if head in ("发码", "send", "sendcode"):
        if len(parts) < 2:
            print("  用法：发码 <手机号>")
            return
        await cmd_send_code(parts[1])
        return
    if head in ("手机登录", "sms", "smslogin"):
        if len(parts) < 3:
            print("  用法：手机登录 <手机号> <验证码>")
            return
        await cmd_medal_missing_by_phone(parts[1], parts[2], interactive=interactive)
        return
    if head in ("重查", "recheck"):
        token = _load_cached_token()
        if not token:
            print("  无缓存 token，请先用「手机登录 <手机号> <验证码>」登录一次")
            return
        await _medal_missing_with_token(token, interactive=interactive)
        return
    if head in ("清缓存", "cleartoken"):
        try:
            TOKEN_CACHE.unlink()
            print("  已清除缓存的 token")
        except FileNotFoundError:
            print("  无缓存 token")
        return

    command = parse_command(text)
    action = command.action
    if action == "medal_view":
        await cmd_medal_view()
    elif action == "medal_refresh":
        await cmd_medal_refresh()
    elif action == "medal_missing":
        token = command.account_selector or ""
        if token and token != "主账号":
            await _medal_missing_with_token(token, interactive=interactive)
        elif interactive:
            print("  F2 缺章需要登录森空岛账号，选择方式：")
            print("    1. 直接粘贴 account_token")
            print("    2. 手机号 + 短信验证码（与 bot 绑定流程一致）")
            cached = _load_cached_token()
            if cached:
                print("    3. 用已缓存的 token 重查")
            choice = input("  回复编号（取消退出）: ").strip()
            if choice == "1":
                token = input("  请粘贴 account_token: ").strip()
                if token:
                    await _medal_missing_with_token(token, interactive=interactive)
            elif choice == "2":
                phone = input("  请输入手机号: ").strip()
                if not (phone.isdigit() and len(phone) == 11):
                    print("  手机号格式不正确")
                    return
                if await cmd_send_code(phone):
                    code = input("  请输入收到的验证码: ").strip()
                    if code:
                        await cmd_medal_missing_by_phone(phone, code, interactive=interactive)
            elif choice == "3" and cached:
                await _medal_missing_with_token(cached, interactive=interactive)
        else:
            print("  单次模式 F2 用法：")
            print("    奖章 缺章 <token>            直接用 token")
            print("    发码 <手机号>                第一步：发验证码")
            print("    手机登录 <手机号> <验证码>    第二步：换 token、缓存、查缺章")
            print("    重查                         用缓存 token 重新查（调试）")
    else:
        print(f"  本工具仅支持奖章命令（解析结果 action={action}）。")
        print("  可用：奖章 | 奖章 刷新 | 奖章 缺章 | 发码 | 手机登录 | 重查")


async def repl() -> None:
    print("=" * 56)
    print("  蚀刻章/奖章 · 命令行手动测试（无需 QQ 协议端）")
    print("=" * 56)
    print("  奖章|奖章 刷新|奖章 缺章|发码|手机登录|重查|帮助|退出")
    print(f"  图片输出目录: {OUT}")
    print("-" * 56)
    while True:
        try:
            text = input("\n输入命令> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in ("退出", "exit", "quit", "q"):
            break
        if text.lower() in ("帮助", "help", "?"):
            print("  奖章         查看蚀刻章统计图（读快照，秒回）")
            print("  奖章 刷新    重新抓取 AKEData 数据并对比上一游戏版本")
            print("  奖章 缺章    个人缺章图（交互选 token / 手机号 / 缓存重查）")
            print("  发码 <手机号>          发送森空岛登录验证码")
            print("  手机登录 <手机号> <验证码>  换 token、缓存、查缺章")
            print("  重查                   用缓存 token 重新查缺章（调试）")
            continue
        try:
            await dispatch(text, interactive=True)
        except EndfieldAPIError as exc:
            print(f"  接口错误: {exc}")
        except Exception:
            print("  发生异常：")
            traceback.print_exc()


async def main() -> None:
    args = sys.argv[1:]
    try:
        if args:
            await dispatch(" ".join(args), interactive=False)
        else:
            await repl()
    finally:
        await close_http_client()
        await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
