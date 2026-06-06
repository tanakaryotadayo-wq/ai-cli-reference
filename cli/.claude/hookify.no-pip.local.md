---
name: no-pip
enabled: true
event: bash
pattern: pip\s+(install|uninstall|freeze)
action: block
---

`pip` は使わないこと。`uv` を使うこと:
- インストール: `uv add パッケージ名`
- 削除: `uv remove パッケージ名`
- 実行: `uv run コマンド`
