---
name: no-uvicorn
enabled: true
event: bash
pattern: uvicorn
action: block
---

`uvicorn` は使わないこと。`granian` を使うこと:
- 例: `granian --interface asgi --host 0.0.0.0 --port 8000 --reload main:app`
