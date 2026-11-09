# AI Release Management for Snowflake

A weekly email showing every AI model your account uses, which ones are being retired, the users and agents affected, and what to swap to. It also lists new GA/Preview features and behavior change bundles.
It runs as a **Cortex Code automation** in Snowflake, and its behavior lives in a plain-English prompt that anyone can edit.

**Open [`README.html`](README.html) for the illustrated 5-step guide.**

## Setup (about 10 minutes, once per account)
1. **Marketplace:** get the free **Snowflake Documentation** listing.
2. **Sign in:** sign in to Snowsight as the service user that will run it, and make sure every recipient's email is verified.
3. **Worksheet (ACCOUNTADMIN):** run [`setup.sql`](setup.sql). It creates the email channel and grants, after you edit the recipients and role.
4. **Cortex Code:** paste [`COCO_PASTE.txt`](COCO_PASTE.txt) (edit the timezone and recipients). It creates, tests and schedules the automation.
5. **Inbox:** the report arrives weekly.

## Files
| File | Purpose |
|---|---|
| `README.html` | Step-by-step guide |
| `setup.sql` | Email integration and grants (about 10 lines) |
| `COCO_PASTE.txt` | The message to paste into Cortex Code |
| `automation-prompt.md` | The weekly instructions in plain English (already inside `COCO_PASTE.txt`); edit this to change behavior |
| `sample-email.html` | Example report (anonymized) |
| `email-to-customer.md` | Cover email template |

## Notes
- The automation runs read-write because sending to several users (`SYSTEM$SEND_EMAIL`) and the docs search need it. The prompt restricts it to read-only queries plus one email.
- Deprecation dates and suggested replacements are read from Snowflake docs by AI. Check them against the linked doc before acting.
