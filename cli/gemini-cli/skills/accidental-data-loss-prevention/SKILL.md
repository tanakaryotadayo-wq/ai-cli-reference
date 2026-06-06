---
name: accidental-data-loss-prevention
description: |
  **STOP AND VERIFY**: Before running any command or tool that results in irreversible data loss, you MUST obtain explicit user consent.
  When in doubt, ask. It is better to wait for confirmation than to accidentally delete production data or critical project assets.
  Use this for:
  - SQL: DROP TABLE/VIEW/SCHEMA/DATABASE, TRUNCATE, or broad DELETE (missing WHERE or using 1=1).
  - Cloud Storage: gsutil rm or gcloud storage rm targeting production data or critical buckets.
  - Infrastructure: gcloud projects delete, deleting Spanner/BigQuery/Dataproc resources, deleting secrets, or KMS key destruction.
license: Apache-2.0
metadata:
  version: v2
  publisher: google
---

# Accidental Data Loss Prevention (不可逆データ損失防止ルール)

データベースの削除やインフラ資源の破棄といった不可逆な操作を行う前に、必ずユーザーの明示的な同意を得てデータの偶発的損失を防ぐ。

## Golden Rule (曖昧性収縮定理)

実行しようとするコマンドや操作が不可逆なデータ損失を招く恐れが少しでもある場合、または対象の重要性や影響範囲に曖昧さがある場合は、独自の判断で決して処理を進めてはならない (MUST NOT)。必ず対象リソース名と影響を明確にし、ユーザーの明示的な同意を取得しなければならない (MUST)。

## Stop Rule (散逸停止定理)

ユーザーへの承認確認中、または承諾要請に対する応答が得られずタイムアウト（180秒）に達した場合、あるいは確認プロセスにおいて何らかのエラーが連続して **5回以上** 発生した場合は、安全側に倒して操作の実行を即座にキャンセルし、処理を異常終了しなければならない (MUST)。

## Task Execution Workflow (最小作用ワークフロー定理)

不可逆な操作を検知した際、エージェントは以下の手順を厳格に実行しなければならない (MUST)。

1. **操作の検知**: 実行予定のコマンドやクエリに、不可逆なデータ損失を招くキーワード（SQLの `DROP`, `TRUNCATE`, `DELETE` 等、またはクラウドの `rm`, `delete` 等）が含まれていないか走査・特定する。
2. **実行の即時停止**: 該当する操作を検出した場合、コマンドの自動実行を即座に停止（ホールド）する。
3. **承諾要求の発話**: ユーザーに対し、以下の情報を明示した上で、実行の是非について明示的な同意（承認）を求める。
   - 削除・破壊される対象（DB、ストレージ、シークレット等）およびそのパス。
   - この操作がなぜ必要であるかの技術的理由。
   - 実行によって生じる影響（データ復旧不可など）。
4. **確認と実行判断**: ユーザーからの返答を待機し、肯定的な同意（例: 「実行してよい」等）が得られた場合のみ実行に進む。拒否された場合、またはタイムアウトした場合は直ちに処理を破棄し安全に終了する。
