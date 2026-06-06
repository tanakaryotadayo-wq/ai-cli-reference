---
name: deletion-justification
enabled: true
event: bash
pattern: rm\s+
action: warn
---

ファイル/ディレクトリを削除しようとしている。
実行前に必ずユーザーに以下を伝えること:

1. **削除するもの**: 何を削除するか
2. **メリット**: 削除することで得られるもの
3. **デメリット**: 削除することで失われるもの・リスク

ユーザーの判断を待ってから削除すること。
