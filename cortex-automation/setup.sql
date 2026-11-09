-- =====================================================================
--  AI Release Management  |  one-time setup  |  run as ACCOUNTADMIN
--  Edit the recipient list, select all, run.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- 1. Email channel: list everyone who should receive the report.
--    Each address must belong to a verified Snowflake user in this account.
CREATE OR REPLACE NOTIFICATION INTEGRATION AI_RELEASE_MGMT_EMAIL
  TYPE = EMAIL
  ENABLED = TRUE
  ALLOWED_RECIPIENTS = ('person1@company.com', 'person2@company.com');   -- <-- EDIT

-- 2. Let the role that runs the automation use the email channel and read usage data.
--    Replace SVC_ROLE with the default role of the user who will create the automation.
GRANT USAGE ON INTEGRATION AI_RELEASE_MGMT_EMAIL TO ROLE SVC_ROLE;    -- <-- EDIT
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE SVC_ROLE;     -- <-- EDIT
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_DOCUMENTATION TO ROLE SVC_ROLE;  -- <-- EDIT

-- 3. Check: should show the integration as enabled.
SHOW NOTIFICATION INTEGRATIONS LIKE 'AI_RELEASE_MGMT_EMAIL';
