# Option A: Cortex Code automation (prompt-based) — recommended

The weekly job is a plain-English prompt run by a Cortex Code automation in Snowflake. When Snowflake renames models or changes doc pages, you fix it by editing the prompt text, not code.

Illustrated guide: open [`README.html`](README.html).

## Deploy (about 10 minutes, once per account)

| # | Where | Do this |
|---|---|---|
| 1 | Snowsight → Marketplace | Search **Snowflake Documentation** → **Get** (keep the name `SNOWFLAKE_DOCUMENTATION`). Skip if you already have it. |
| 2 | Snowsight | Sign in as the **service user** that will run the automation (it must be able to sign in to Snowsight). Make sure every recipient's email is verified under Settings → Profile. |
| 3 | SQL worksheet (ACCOUNTADMIN) | Paste [`setup.sql`](setup.sql). Edit `ALLOWED_RECIPIENTS` and `SVC_ROLE` (the service user's default role), then **Run All**. |
| 4 | Cortex Code in Snowsight | Paste all of [`COCO_PASTE.txt`](COCO_PASTE.txt) after editing the timezone and recipients lines. Cortex Code creates the automation paused, runs one test (the email arrives), then asks to start the schedule. Answer **Yes**. |
| 5 | Inbox | Everyone on the list gets the report weekly. |

## Files
| File | Purpose |
|---|---|
| `setup.sql` | Email integration and grants |
| `COCO_PASTE.txt` | The one message to paste into Cortex Code (contains the prompt) |
| `automation-prompt.md` | The prompt by itself, for reading and editing |
| `sample-email.html` | Example output (anonymized) |
| `README.html` | Step-by-step guide |

## Manage (ask Cortex Code)
- "Run AI_RELEASE_MANAGEMENT now"
- "Change AI_RELEASE_MANAGEMENT to every Friday at 9am"
- "Update the AI_RELEASE_MANAGEMENT prompt to also …"
- "Pause AI_RELEASE_MANAGEMENT" / "Drop AI_RELEASE_MANAGEMENT", then `DROP INTEGRATION AI_RELEASE_MGMT_EMAIL;`
- **Add recipients:** add them to `ALLOWED_RECIPIENTS` in `setup.sql`, re-run it, then update `RECIPIENTS` in the prompt.

## Notes
- **Runs as:** the user who created it, read-write. That's required for emailing several users and for the docs search. The prompt limits it to read-only queries plus one email, but nothing technically enforces that, so use a limited-privilege service role.
- **Results can vary slightly between runs.** The agent reads the docs each week, and its swap-to models are its own suggestions when the docs name none. Check dates against the linked doc before acting.
