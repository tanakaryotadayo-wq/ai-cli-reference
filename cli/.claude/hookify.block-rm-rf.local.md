---
name: block-rm-rf
enabled: true
event: bash
pattern: rm\s+(-rf|-fr|-r\s+-f|-f\s+-r)
action: block
---

`rm -rf` は危険。実行をブロックした。
削除が必要な場合はユーザーに確認を取ること。
