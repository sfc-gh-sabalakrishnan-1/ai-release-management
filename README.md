# AI Release Management for Snowflake

A weekly email showing every AI model your account uses, which ones are being retired, the users and agents affected, and what to swap to. It also lists new GA/Preview features and behavior change bundles. Everything runs inside Snowflake.

There are two ways to deploy it. **Pick one.**

| | [`cortex-automation/`](cortex-automation/) — **recommended** | [`snowflake-task/`](snowflake-task/) |
|---|---|---|
| How it runs | Cortex Code automation follows a plain-English prompt | Python stored procedure run by a Snowflake task |
| Setup | `setup.sql` + one message pasted into Cortex Code | One `setup.sql` |
| Changing it | Edit the prompt text, no code | Edit Python/SQL |
| When docs or model names change | Agent adapts; fix by rewording the prompt | Parsing can break; needs a developer |
| Email format | Template in the prompt; very close each week | Identical each week |
| Recipients | Multiple (via email integration) | Multiple (via email integration) |
| Runs as | The user who created it (use a service user) | Task owner role |

Each folder has its own deployment instructions in **`DEPLOY.md`** and an illustrated **`README.html`**.

`email-to-customer.md` is a cover email template for sending the kit.

Deprecation dates and suggested replacements are read from Snowflake docs by AI. Check them against the linked doc before acting.
