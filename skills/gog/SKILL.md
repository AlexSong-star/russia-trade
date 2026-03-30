---
name: gog
description: Google Workspace CLI for Gmail, Calendar, Drive, Contacts, Sheets, and Docs.
homepage: https://gogcli.sh
metadata: {"clawdbot":{"emoji":"🎮","requires":{"bins":["gog","python3"]},"install":[{"id":"brew","kind":"brew","formula":"steipete/tap/gogcli","bins":["gog"],"label":"brew install steipete/tap/gogcli"}]}}
---

# gog (Google Workspace CLI)

Use `gog-auth` (auto-refresh wrapper) for Gmail/Calendar/Drive/Contacts/Sheets/Docs.

**重要：** gog 原生命令需要手动传 `--access-token`，使用 `gog-auth` 自动刷新 token，更方便。

## Auto-Refresh Wrapper (推荐)

一个 `gog-auth` wrapper 已部署在 `/usr/local/bin/gog-auth`，自动用 refresh_token 刷新 access_token。

## Common Commands (用 gog-auth)

```bash
# Gmail
gog-auth gmail search 'newer_than:7d' --max 10
gog-auth gmail search 'from:xxx@gmail.com' --max 5
gog-auth gmail send --to a@b.com --subject "Hi" --body "Hello"

# Calendar
gog-auth calendar list --max 10
gog-auth calendar events primary --from 2026-03-01 --to 2026-03-31

# Contacts
gog-auth contacts list --max 20

# Drive
gog-auth drive ls --max 10
gog-auth drive search "filename" --max 10

# Sheets
gog-auth sheets get <sheetId> "Sheet1!A1:D10" --json
gog-auth sheets append <sheetId> "Sheet1!A:C" --values-json '[["x","y","z"]]'

# Docs
gog-auth docs export <docId> --format txt --out /tmp/doc.txt
gog-auth docs cat <docId>
```

## 使用 gog 原生命令 (需要 access-token)

Token 刷新: `curl -s -X POST https://oauth2.googleapis.com/token -d "refresh_token=<refresh_token>&client_id=<client_id>&client_secret=<client_secret>&grant_type=refresh_token"`

## Notes

- Confirm before sending mail or creating events
- For scripting, prefer `--json` plus `--no-input`
- Scopes: email, Gmail, Calendar, Contacts, Drive, Docs, Sheets
