# otae Bot Entari

The source project was copied as a read-only migration source. Runtime data,
assets, plugin code, configs, and the real `.env` were copied into this project.

## Run Locally

```powershell
cd C:\Code\qqbot\bot-entari
.\scripts\setup.ps1
.\scripts\start.bat
```

Direct start:

```powershell
.\.venv\Scripts\python.exe bot.py
```

## Satori

The entrypoint reads `SATORI_CLIENTS` from `.env`. Each object in the list creates
one Satori WebSocket connection, so one Entari backend can connect to multiple
LLOneBot accounts/endpoints:

```dotenv
SATORI_CLIENTS=[{"host":"127.0.0.1","port":5500,"path":"","token":"TOKEN_1"},{"host":"127.0.0.1","port":5501,"path":"","token":"TOKEN_2"}]
```

Use the Satori WebSocket port and token configured in each LLOneBot instance.
When several instances run on the same host, give them different ports. If the
Satori server exposes several logins through one endpoint, that endpoint only
needs one list entry. `entari.yml` is not the network source for this custom
`bot.py` entrypoint.

## Deploy To Windows Server

Default production directory:

```text
D:\Bot\BotEntari
```

Deploy from the development directory:

```powershell
cd C:\Code\qqbot\bot-entari
.\scripts\deploy.ps1 -Prod
```

On the server:

```powershell
cd D:\Bot\BotEntari
.\scripts\setup.ps1
.\scripts\start.bat
```
