# Option B: Snowflake task (code-based)

A Python stored procedure builds the email with a fixed layout, and a weekly Snowflake task runs it. There's no Cortex Code step; one SQL file does everything.

Illustrated guide: open [`README.html`](README.html).

## Deploy (about 10 minutes, once per account)

| # | Where | Do this |
|---|---|---|
| 1 | Snowsight → Marketplace | Search **Snowflake Documentation** → **Get** (keep the name `SNOWFLAKE_DOCUMENTATION`). Skip if you already have it. |
| 2 | Snowsight | Make sure every recipient's email is verified (Settings → Profile). |
| 3 | SQL worksheet (ACCOUNTADMIN) | Paste [`setup.sql`](setup.sql). Edit the 3 lines at the top: `recipients` (comma-separated, no spaces), `warehouse`, `schedule`. |
| 4 | Same worksheet | Select all → **Run**. It creates the `AI_MODEL_WATCH` database, the `SEND_REPORT` procedure, the `AI_MODEL_WATCH_EMAIL` integration and the `WEEKLY_REPORT` task, then sends the first email (about 2 minutes). |
| 5 | Inbox | Everyone on the list gets the report on the schedule. |

## Files
| File | Purpose |
|---|---|
| `setup.sql` | Everything, with the procedure code embedded |
| `src/report.py` | The same procedure code, for reading and editing |
| `sample-email.html` | Example output (anonymized) |
| `README.html` | Step-by-step guide |

## Manage
```sql
EXECUTE TASK AI_MODEL_WATCH.CORE.WEEKLY_REPORT;                       -- send now
ALTER TASK AI_MODEL_WATCH.CORE.WEEKLY_REPORT SUSPEND;                 -- pause (RESUME to restart)
-- change recipients/schedule: edit the 3 lines and re-run setup.sql
DROP DATABASE AI_MODEL_WATCH; DROP INTEGRATION AI_MODEL_WATCH_EMAIL;  -- remove
```

## Notes
- **Layout:** the email format is identical every week. Deprecation dates and replacements are still read from the docs by `AI_COMPLETE`.
- **Maintenance:** changes need Python/SQL edits in `src/report.py`, copied into `setup.sql`. Model renames or doc format changes can break the parsing (for example, the name matching and hard-coded-object patterns).
- **Known issue:** this version flagged base `llama3.1-8b` as legacy, but the docs list only `llama3.1-8b (fine-tuned)`. Check fine-tuned vs. base models against the doc link. The Cortex Code automation version reads this correctly.
