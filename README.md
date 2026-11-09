# AI Release Management for Snowflake

A weekly email showing every AI model your account uses, which ones are being retired, the users and agents affected, and what to swap to. It also lists new GA/Preview features and behavior change bundles. Everything runs inside Snowflake, so you only need Snowsight.

**Open [`README.html`](README.html) for the illustrated 5-step guide.**

## Setup (about 10 minutes, once per account)

1. **Marketplace:** get the free **Snowflake Documentation** listing and keep the name `SNOWFLAKE_DOCUMENTATION`.
2. **Profile:** verify the email address of every recipient (Settings → Profile).
3. **Worksheet (ACCOUNTADMIN):** paste [`setup.sql`](setup.sql) and edit the top 3 lines: recipients, warehouse, schedule.
4. **Run all.** The first report is sent in about 2 minutes.
5. **Inbox:** the report repeats on your schedule.

## Files

| File | Purpose |
|---|---|
| `README.html` | Step-by-step guide |
| `setup.sql` | The only file you run |
| `sample-email.html` | Example report (anonymized) |
| `src/report.py` | Report source (already embedded in `setup.sql`) |
| `email-to-customer.md` | Cover email template |

## Manage

```sql
EXECUTE TASK AI_MODEL_WATCH.CORE.WEEKLY_REPORT;                -- send now
ALTER TASK AI_MODEL_WATCH.CORE.WEEKLY_REPORT SUSPEND;          -- pause (RESUME to restart)
DROP DATABASE AI_MODEL_WATCH; DROP INTEGRATION AI_MODEL_WATCH_EMAIL;  -- remove
```

Deprecation dates and replacement models are extracted from Snowflake docs by an AI model. Check each one against the linked doc before acting.
