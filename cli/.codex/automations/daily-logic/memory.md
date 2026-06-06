# Daily Logic Memory

## 2026-03-07 Run 1
- Workspace scan completed (docs, migrations, app runtime, orchestration files).
- Source-of-truth candidates confirmed: `migrations/*.sql`, `app/`, `tests/integration/`, `pyproject.toml`+`uv.lock`, `EXECUTION_KERNEL_MANUAL_v1.1.md`.
- Main fragmentation found:
  - Duplicate runbook surfaces (`README.md` vs `RUNBOOK.md` vs `docs/concept_compiler_runbook.md`).
  - Legacy/conflicting drafts (`EXECUTION_KERNEL_MANUAL_v1.0.md`, `n8n-compose.yml`, `n8n-workflow-pcc-loop.json`, `database.py` conceptual schema).
  - Scheduler duplication risk (internal loops in `app/services/scheduler.py` + external Inngest batch endpoints).
- Notable conflict/risk:
  - `RUNBOOK.md` contains destructive rollback examples (`git reset --hard`), conflicting with safer operations posture.
  - `README.md` still says Inngest/pg_cron integration is next while Inngest artifacts already exist.
- Recommended next focus:
  1) Define doc SoT and archive legacy docs/workflows.
  2) Replace unsafe rollback guidance with safe revert flow.
  3) Unify scheduler ownership + idempotency lock to avoid double recover execution.

Runtime note: ~15 minutes analysis pass.

## 2026-03-08 Run 2
- Reviewed docs/code/migrations for fragmentation with focus on SoT preservation.
- Confirmed repeated conflicts:
  - Migration ordering ambiguity: duplicate numeric prefixes (`018_*`, `019_*`, `020_*`) with runner applying lexicographic glob (`migrations/*.sql`), while runbooks still claim 22 files (actual 25).
  - Scheduler ownership split across internal async loops (`app/services/scheduler.py`) and external Inngest cron functions (`inngest/*.function.ts`), plus README wording that still treats integration as future work.
  - Operational documentation sprawl across `README.md`, `RUNBOOK.md`, `RUNBOOK_CLOUDRUN.md`, and `docs/concept_compiler_runbook.md` with overlapping startup/migration/ops instructions.
  - Legacy/spec drift surfaces (`EXECUTION_KERNEL_MANUAL_v1.0.md`, `n8n-*`, proposal-heavy PCC docs) mixed with active implementation docs.
- Promote candidates: `EXECUTION_KERNEL_MANUAL_v1.1.md`, `docs/dod_checklist.md`, `migrations/*.sql` + `migrations/000_runner.sh`, `app/` + `tests/` runtime behavior.
- Archive candidates: `n8n-compose.yml`, `n8n-workflow-pcc-loop.json`, v1.0 manual to explicit frozen archive path, proposal docs grouped under proposals namespace.
- Highest-value next tasks: migration sequence normalization, scheduler ownership unification + idempotency lock, runbook/README SoT consolidation with safe rollback guidance.

Runtime note: ~22 minutes (ended 2026-03-08T00:02:51Z).

## 2026-03-11 Run 3
- Re-scanned workspace with emphasis on shell/DB SoT fragmentation.
- Confirmed unresolved duplication/conflict:
  - Migration sequence ambiguity remains: duplicate numeric prefixes (`018_*`, `019_*`, `020_*`) while `migrations/000_runner.sh` executes `migrations/*.sql` lexicographically; runbooks still state "22 files" though current SQL migrations are 25.
  - Scheduler ownership still split: internal startup loops in `app/main.py` (`recover_stuck_loop`, `partition_check_loop`) and external Inngest cron functions (`inngest/recover_stuck.function.ts`, `inngest/cold_storage_export.function.ts`).
  - Operational docs remain fragmented and partially inconsistent (`README.md`, `RUNBOOK.md`, `RUNBOOK_CLOUDRUN.md`, `docs/concept_compiler_runbook.md`).
  - Legacy draft surfaces still mixed with active workspace (`n8n-compose.yml`, `n8n-workflow-pcc-loop.json`, `EXECUTION_KERNEL_MANUAL_v1.0.md`, conceptual `database.py` that can drift from migration SoT).
- Promote-to-master candidates reaffirmed:
  - DB SoT: `migrations/*.sql` + `migrations/000_runner.sh`
  - Runtime SoT: `app/main.py`, `app/services/*`, `tests/` and `tests/integration/`
  - Operating manual SoT: `EXECUTION_KERNEL_MANUAL_v1.1.md` (single canonical manual)
- Archive candidates reaffirmed:
  - `n8n-compose.yml`, `n8n-workflow-pcc-loop.json`, `EXECUTION_KERNEL_MANUAL_v1.0.md` (frozen archive namespace)
  - proposal-heavy docs grouped under explicit proposals namespace to avoid runbook bleed.
- Highest-value next tasks unchanged in priority:
  1) Normalize migration ordering to deterministic monotonic sequence and align runbook counts.
  2) Enforce single scheduler authority (internal OR Inngest) plus DB-level idempotency lock for batch recovery/export calls.
  3) Consolidate runbooks into one ops index that routes to canonical local/cloud procedures and remove unsafe rollback examples.

Runtime note: ~20 minutes analysis pass (ended 2026-03-11T01:24:42Z).
