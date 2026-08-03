# 森空岛终末地公开数据独立查询

独立脚本：`scripts/query_skland_endfield.py`。

脚本复用现有 `.runtime/skland_reverse/session_sensitive.json`，自动刷新签名上下文，查询终末地个人详情、危机合约和影拓丰碑，并生成原始 JSON、脱敏 JSON 与 Markdown 摘要。

## 通过昵称定位内部用户 ID

不能把 Web 公开主页 ID 直接传给绑定接口。先调用原生用户搜索：

```http
GET /api/v1/user/search?keyword=<昵称>&kind=1&pageNumber=1&pageSize=20
```

从精确昵称结果中取得内部用户 ID，再执行：

```powershell
python scripts\query_skland_endfield.py `
  --user-id <INTERNAL_USER_ID> `
  --label target
```

`--user-id` 是森空岛原生内部用户 ID，不是 Web/IM 公开 ID、森空岛 showId、终末地游戏 UID 或 roleId。

## 已知角色时直接查询

```powershell
python scripts\query_skland_endfield.py `
  --role-id <ROLE_ID> `
  --server-id 1 `
  --label target
```

查询其他用户时推荐使用 `--user-id`，脚本会先查询绑定并在详情请求中附带 `userId=<INTERNAL_USER_ID>`。

## 血狼破军复查结果

- 森空岛昵称：`血狼破军`
- 原生内部用户 ID：`101126`
- Web/IM 公开 ID：`3002521479368`
- hgId：`893109180714`
- 终末地游戏 UID：`618965353`
- 终末地 roleId：`1334382133`
- serverId：`1`

个人详情接口返回 `code: 0`，角色等级 60、世界等级 7、主线“志同道合”，拥有 28 名干员、59 件武器、321 项档案。

危机合约与影拓丰碑接口也返回 `code: 0`，但当前业务字段分别为 `crisisContract: null` 和 `indieHard: null`。这表示接口和账号定位均正常，只是当前没有可公开展示的记录，或对应展示配置尚未开启。

## 输出

```text
.runtime/skland_reverse/responses/public_<label>_binding_sensitive.json
.runtime/skland_reverse/responses/public_<label>_detail_sensitive.json
.runtime/skland_reverse/responses/public_<label>_crisis_contract_sensitive.json
.runtime/skland_reverse/responses/public_<label>_indie_hard_sensitive.json
.runtime/skland_reverse/responses/redacted_public_<label>_*.json
.runtime/skland_reverse/responses/public_<label>_summary.md
```

真实会话、原始响应和内部用户 ID 只保存在 `.runtime`，不要提交到 Git 或发送到 Bot 公共消息。
