**Subject:** AI Release Management: weekly report, 10-minute setup

Hi <Name>,

Here is the simple setup we discussed. Every week you get one email that shows:

- Every AI model used in your account, and which ones are being retired (with a timeline chart)
- For each affected model: the users, the agents and functions, the last call, and the model to swap to
- Before/after code, plus a list of procedures, functions and views to update
- New GA and Preview features and behavior change bundles, with doc links

**Setup:** follow the 5 steps in the attached `README.html`. It's all done in Snowsight with one SQL file, takes about 10 minutes, and runs inside Snowflake from then on. For multiple accounts, repeat it in each account.

`sample-email.html` shows what the report looks like.

Happy to walk through it on a quick call.

Best,
<Your name>

*Attachments: README.html, setup.sql, sample-email.html*
