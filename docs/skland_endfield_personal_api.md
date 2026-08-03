# 森空岛「明日方舟：终末地」个人数据接口

> 逆向与本机复现日期：2026-07-11；合约记录详情补充实测：2026-07-15  
> 森空岛 App：`com.hypergryph.skland` `1.57.0`  
> 结论：验证码登录、OAuth 授权、`cred` 换取、签名刷新、角色绑定查询、终末地个人详情查询均已返回 `code: 0`。

## 1. 结论摘要

主接口：

```http
GET https://zonai.skland.com/api/v1/game/endfield/card/detail?roleId=<ROLE_ID>&serverId=<SERVER_ID>
```

必要认证头：

```http
cred: <REDACTED>
platform: 3
timestamp: <SERVER_ALIGNED_UNIX_SECONDS>
vName: 1.0.0
sign: <DYNAMIC_MD5_SIGNATURE>
```

`dId` 可作为数美设备 ID 发送；本机实测在请求头省略 `dId`、但签名对象中保留 `"dId":""` 时请求成功。

主接口响应数据位于：

```text
data.detail
```

## 2. 验证状态

### 2.1 已实测成功

以下请求已在本机直接发出，并收到 `code: 0`：

| 步骤 | 方法与路径 | 用途 |
|---|---|---|
| 发送短信 | `POST https://as.hypergryph.com/general/v1/send_phone_code` | 发送登录验证码 |
| 验证码登录 | `POST https://as.hypergryph.com/user/auth/v1/token_by_phone_code` | 获取鹰角通行证 token |
| OAuth 授权 | `POST https://as.hypergryph.com/user/oauth2/v2/grant` | 获取森空岛 OAuth code |
| 换取凭据 | `POST https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code` | 获取 `cred` 和初始化 token |
| 刷新签名 | `GET https://zonai.skland.com/web/v1/auth/refresh` | 获取当前签名 token 和服务器时间 |
| 查询绑定 | `GET https://zonai.skland.com/api/v1/game/player/binding` | 获取 `roleId`、`serverId` |
| 查询详情 | `GET https://zonai.skland.com/api/v1/game/endfield/card/detail` | 获取完整个人数据 |
| 查询危机合约 | `GET https://zonai.skland.com/api/v1/game/endfield/card/crisis-contract` | 获取活动状态、历史与最佳记录 ID |
| 查询合约记录详情 | `GET https://zonai.skland.com/api/v1/game/endfield/card/crisis-contract/record` | 用 `recordId` 获取当次武器、词条等级和装备快照 |
| 查询影拓丰碑 | `GET https://zonai.skland.com/api/v1/game/endfield/card/indie-hard` | 获取主题、关卡与最佳记录 |

本次验证摘要保存在本地忽略目录：

```text
.runtime/skland_reverse/responses/verification_summary.json
```

### 2.2 静态确认、未逐个实测

```text
GET  /api/v1/game/endfield/card/char
POST /api/v1/game/endfield/card/detail/char-sort
POST /api/v1/game/endfield/card/detail/show-config

GET  /api/v1/gameplat/list
GET  /api/v1/game/player/info
GET  /api/v1/game/player/show-config
POST /api/v1/game/player/show-config
POST /api/v1/game/player/asset-show
POST /api/v1/gameplat/game/refresh
```

合约记录详情请求参数：

```http
GET /api/v1/game/endfield/card/crisis-contract/record?roleId=<ROLE_ID>&serverId=<SERVER_ID>&recordId=<BEST_RECORD_ID>
```

`recordDetail.chars[]` 会返回记录当时的 `weapon.icon`、`weapon.level`、`weapon.weaponTerms[3]`、`equips` 四槽、`level`、`potentialLevel` 和 `avatarUrl`。列表接口中的 `bestRecord.chars[]` 只有角色 ID、等级、潜能和头像，不能用于还原历史配装。

## 3. 官方验证码登录链路

### 3.1 发送验证码

```http
POST https://as.hypergryph.com/general/v1/send_phone_code
Content-Type: application/json

{
  "phone": "<PHONE>",
  "type": 1
}
```

`type: 1` 表示登录验证码。

### 3.2 验证码换登录 token

```http
POST https://as.hypergryph.com/user/auth/v1/token_by_phone_code
Content-Type: application/json

{
  "phone": "<PHONE>",
  "code": "<SMS_CODE>"
}
```

成功后读取：

```text
data.token
```

### 3.3 OAuth 授权给森空岛

```http
POST https://as.hypergryph.com/user/oauth2/v2/grant
Content-Type: application/json

{
  "token": "<HG_TOKEN>",
  "appCode": "4ca99fa6b56cc2ba",
  "type": 0
}
```

成功后读取：

```text
data.code
```

### 3.4 OAuth code 换森空岛 cred

```http
POST https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code
Content-Type: application/json

{
  "kind": 1,
  "code": "<OAUTH_CODE>"
}
```

成功响应包含：

```text
data.cred
data.userId
data.token
timestamp
```

真实手机号、短信验证码、OAuth code、token 和 `cred` 不应写入日志、Git 或 Bot 对外消息。

## 4. 刷新签名上下文

请求业务接口前先刷新：

```http
GET https://zonai.skland.com/web/v1/auth/refresh
cred: <REDACTED>
```

该接口不需要 `sign`。成功响应包含：

```json
{
  "code": 0,
  "timestamp": "<SERVER_UNIX_SECONDS>",
  "data": {
    "token": "<SIGN_TOKEN>"
  }
}
```

保存刷新完成时的本地时间：

```text
clientTime = floor(localUnixSeconds)
serverTime = response.timestamp
```

后续请求时间戳按前端逻辑计算：

```text
timestamp = serverTime + (floor(localUnixSecondsNow) - clientTime)
```

不要长期固定使用 refresh 响应中的原始 `timestamp`，否则会返回：

```text
code: 10003
message: 请勿修改设备本地时间
```

## 5. 正确签名算法

### 5.1 Canonical string

```text
canonical =
  path
  + (method == "GET" ? rawQueryWithoutQuestionMark : rawBody)
  + timestamp
  + JSON.stringify({
      platform,
      timestamp,
      dId,
      vName
    })
```

规则：

- `path` 只包含 URL path，例如 `/api/v1/game/player/binding`。
- GET 使用原始 query，不能包含开头的 `?`。
- POST 使用实际发送的原始 JSON body 字符串。
- query 参数顺序和编码必须与最终 URL 完全一致。
- JSON 必须紧凑序列化，不能插入空格。
- 即使请求头未发送 `dId`，签名 JSON 中也要保留 `"dId":""`。

### 5.2 摘要算法

```text
hmacHex = HMAC-SHA256(canonical, signToken).hexdigest()
sign = MD5(hmacHex).hexdigest()
```

关键点：二次摘要是 **MD5**，不是 SHA-256。对应前端 webpack 模块：

- `3793` 导出 `CryptoJS.HmacSHA256`
- `84636` 导出 `CryptoJS.MD5`

### 5.3 Python 实现

```python
import hashlib
import hmac
import json


def make_sign(path, method, query, body, timestamp, sign_token):
    sign_headers = {
        "platform": "3",
        "timestamp": str(timestamp),
        "dId": "",
        "vName": "1.0.0",
    }
    canonical = (
        path
        + (query if method == "GET" else body)
        + str(timestamp)
        + json.dumps(sign_headers, separators=(",", ":"))
    )
    hmac_hex = hmac.new(
        sign_token.encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hashlib.md5(hmac_hex.encode()).hexdigest()
```

## 6. 获取绑定角色

```http
GET https://zonai.skland.com/api/v1/game/player/binding
cred: <REDACTED>
platform: 3
timestamp: <SERVER_ALIGNED_UNIX_SECONDS>
vName: 1.0.0
sign: <DYNAMIC>
```

在响应的 `data.list` 中寻找：

```json
{
  "appCode": "endfield",
  "appName": "明日方舟：终末地",
  "bindingList": [
    {
      "roles": [
        {
          "serverId": "<SERVER_ID>",
          "roleId": "<ROLE_ID>",
          "nickname": "<REDACTED>",
          "level": 0,
          "serverType": "domestic",
          "serverName": "China"
        }
      ]
    }
  ]
}
```

## 7. 获取终末地个人详情

```http
GET https://zonai.skland.com/api/v1/game/endfield/card/detail?roleId=<ROLE_ID>&serverId=<SERVER_ID>
cred: <REDACTED>
platform: 3
timestamp: <SERVER_ALIGNED_UNIX_SECONDS>
vName: 1.0.0
sign: <DYNAMIC>
```

查看其他用户时，前端定义还允许追加：

```text
userId=<SKLAND_USER_ID>
```

本机当前账号查询不需要 `userId`。

成功响应顶层：

```json
{
  "code": 0,
  "message": "OK",
  "timestamp": "<SERVER_UNIX_SECONDS>",
  "data": {
    "detail": {}
  }
}
```

## 8. `data.detail` 字段

### 8.1 基础信息 `base`

| 字段 | 含义 |
|---|---|
| `serverName` | 服务器名称 |
| `roleId` | 游戏角色 ID |
| `name` | 角色名 |
| `createTime` | 角色创建时间 |
| `saveTime` | 数据保存时间 |
| `lastLoginTime` | 最近登录时间 |
| `exp` | 当前经验 |
| `level` | 角色等级 |
| `worldLevel` | 世界等级 |
| `gender` | 性别枚举 |
| `avatarUrl` | 头像 URL |
| `mainMission` | 主线任务信息 |
| `charNum` | 干员数量 |
| `weaponNum` | 武器数量 |
| `docNum` | 文档数量 |

### 8.2 干员 `chars[]`

每个干员包含：

```text
id
wikiItemId
level
evolvePhase
potentialLevel
gender
ownTs
charData
userSkills
bodyEquip
armEquip
firstAccessory
secondAccessory
tacticalItem
weapon
talent
```

`charData` 包含：

```text
id
name
rarity
profession
property
weaponType
tags
skills
abilityTalents
combatTalents
cultivationTalents
avatarRtUrl
avatarSqUrl
illustrationUrl
```

`weapon` 包含：

```text
level
breakthroughLevel
refineLevel
gem
weaponData
wikiItemId
```

### 8.3 其他模块

| 字段 | 结构/用途 |
|---|---|
| `achieve` | 成就奖牌、展示配置、完成数量 |
| `spaceShip.rooms[]` | 舰船房间、等级、入驻干员、报告 |
| `domain[]` | 领地等级、工厂、结算点、资源、收藏品 |
| `dungeon` | 当前理智、理智上限、恢复完成时间 |
| `bpSystem` | 通行证当前等级与上限 |
| `dailyMission` | 每日任务活跃度与上限 |
| `weeklyMission` | 周常分数与上限 |
| `config` | 干员展示、排名展示、展示干员 ID |
| `currentTs` | 当前服务器时间 |
| `quickaccess[]` | 快捷入口名称、图标、链接 |
| `indieHard.indieHardGroups[]` | 独立高难玩法分组 |
| `seekSuspicion` | 当前与最大疑点/搜寻进度 |
| `crisisContract[]` | 危机合约活动、挑战、任务、最高记录、时间范围 |

## 9. Bot 接入流程

推荐将认证和业务查询分开：

1. 管理员通过验证码登录一次，安全保存 `cred`。
2. Bot 每次查询前调用 `/web/v1/auth/refresh`。
3. 保存 `signToken`、`clientTime`、`serverTime` 到内存。
4. 调 `/api/v1/game/player/binding` 解析 `roleId/serverId`，并设置短期缓存。
5. 按最终 URL 的 query 顺序生成签名。
6. 调 `/api/v1/game/endfield/card/detail`。
7. 将 `data.detail` 转为 Bot 内部模型，不把整个原响应直接发送到群聊。

建议错误处理：

| code / 状态 | 处理方式 |
|---|---|
| `0` | 成功 |
| `10003` | 用响应 `timestamp` 重新校时并重试一次 |
| `10000` | 检查 canonical、query 顺序、MD5 二次摘要和 token |
| HTTP `401` | refresh 并重试；仍失败则要求重新登录 |
| HTTP `403` | 检查账号状态、实名认证或访问权限 |

## 10. 本地证据文件

敏感文件，仅限本机：

```text
.runtime/skland_reverse/session_sensitive.json
.runtime/skland_reverse/responses/binding_sensitive.json
.runtime/skland_reverse/responses/endfield_detail_sensitive.json
.runtime/skland_reverse/responses/refresh_sensitive.json
```

脱敏文件：

```text
.runtime/skland_reverse/responses/redacted_binding.json
.runtime/skland_reverse/responses/redacted_endfield_detail.json
.runtime/skland_reverse/responses/redacted_refresh.json
.runtime/skland_reverse/responses/verification_summary.json
```

复现脚本：

```text
.runtime/skland_reverse/hg_sdk/phone_login_gui.py
.runtime/skland_reverse/reproduce_endfield.py
```

以上 `.runtime` 内容应保持 Git 忽略；正式代码和文档中只能使用 `<REDACTED>`、环境变量或安全凭据存储。
