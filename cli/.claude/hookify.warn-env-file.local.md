---
name: warn-env-file
enabled: true
event: file
pattern: \.env
action: warn
---

⚠️ `.env` ファイルを編集しようとしている。
シークレットが含まれている可能性がある。本当に必要か確認してから進めること。
