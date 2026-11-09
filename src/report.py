import datetime as dt
import json
import re
from html import escape as E

DOCS = "SNOWFLAKE_DOCUMENTATION.SHARED.CKE_SNOWFLAKE_DOCS_SERVICE"
LLM = "claude-sonnet-4-5"

SF, NAVY, RED, AMB, BLU, GRN, GRY = "#29B5E8", "#11567F", "#D93025", "#E8A317", "#1A73E8", "#188038", "#5F6368"
PILL = {"RETIRED": RED, "≤30 DAYS": RED, "≤90 DAYS": AMB, "≤180 DAYS": BLU, "LEGACY": AMB,
        "LEGACY SOON": BLU, "SCHEDULED": BLU, "DEPRECATED": RED, "SUPPORTED": GRN}
TH = 'style="text-align:left;padding:8px 10px;background:#F1F5F9;color:#334155;font-size:11px;text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid #E2E8F0"'
TD = "padding:8px 10px;border-bottom:1px solid #EEF2F6;font-size:13px;vertical-align:top;overflow-wrap:anywhere"
MONO = "font-family:Menlo,Consolas,monospace;font-size:12px;white-space:nowrap"
MONO_WRAP = "font-family:Menlo,Consolas,monospace;font-size:12px"
LINK = "color:#0B6FA4;text-decoration:none;font-weight:bold"

USAGE_SQL = """
WITH usage AS (
  SELECT model_name model, 'AI Function' kind, function_name obj, user_id, NULL::varchar user_name, start_time::timestamp_ltz ts
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY WHERE start_time > DATEADD(day,-180,CURRENT_TIMESTAMP())
  UNION ALL
  SELECT model_name, 'AI Function', function_name, NULL, NULL, start_time::timestamp_ltz
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY WHERE start_time > DATEADD(day,-180,CURRENT_TIMESTAMP())
  UNION ALL
  SELECT model_name, 'REST API', 'Cortex REST API', user_id, NULL, start_time::timestamp_ltz
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_REST_API_USAGE_HISTORY WHERE start_time > DATEADD(day,-180,CURRENT_TIMESTAMP())
  UNION ALL
  SELECT m.key, 'Agent', a.agent_database_name||'.'||a.agent_schema_name||'.'||a.agent_name, a.user_id, a.user_name, a.start_time::timestamp_ltz
  FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY a,
       LATERAL FLATTEN(a.tokens_granular) g, LATERAL FLATTEN(g.value) r, LATERAL FLATTEN(r.value:cortex_agents) m
  WHERE a.start_time > DATEADD(day,-180,CURRENT_TIMESTAMP())
  UNION ALL
  SELECT m.key, 'Snowflake Intelligence', s.agent_name, s.user_id, s.user_name, s.start_time::timestamp_ltz
  FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWFLAKE_INTELLIGENCE_USAGE_HISTORY s,
       LATERAL FLATTEN(s.tokens_granular) g, LATERAL FLATTEN(g.value) r, LATERAL FLATTEN(r.value) svc, LATERAL FLATTEN(svc.value) m
  WHERE s.start_time > DATEADD(day,-180,CURRENT_TIMESTAMP()) AND IS_OBJECT(svc.value)
)
SELECT LOWER(u.model) model, u.kind, u.obj,
       COALESCE(u.user_name, us.name, '(system)') user_name, us.email,
       MAX(u.ts)::date last_call, COUNT(*) calls
FROM usage u LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS us ON us.user_id = u.user_id AND us.deleted_on IS NULL
WHERE u.model IS NOT NULL AND u.model <> ''
GROUP BY 1,2,3,4,5
"""

DETAIL_SQL = """-- Every user / agent / function using one model (last 180 days). Change the model name:
SET m = 'mistral-large2';
SELECT CURRENT_ACCOUNT_NAME() account, 'AI Function' type, function_name used_by, u.name user_name, u.email, MAX(start_time) last_call, COUNT(*) calls
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS u ON u.user_id = h.user_id
WHERE h.model_name ILIKE $m AND start_time > DATEADD(day,-180,CURRENT_TIMESTAMP()) GROUP BY ALL
UNION ALL
SELECT CURRENT_ACCOUNT_NAME(), 'Agent', agent_database_name||'.'||agent_schema_name||'.'||agent_name, user_name, NULL, MAX(start_time), COUNT(*)
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY WHERE TO_VARCHAR(tokens_granular) ILIKE '%"'||$m||'"%'
AND start_time > DATEADD(day,-180,CURRENT_TIMESTAMP()) GROUP BY ALL
ORDER BY last_call DESC;"""


def _docs_context(session, queries, limit):
    parts = []
    for q in queries:
        spec = json.dumps({"query": q, "columns": ["SOURCE_URL", "CHUNK"], "limit": limit})
        parts.append(
            "SELECT r.value:SOURCE_URL::string url, LEFT(r.value:CHUNK::string, 1500) chunk "
            f"FROM TABLE(FLATTEN(PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('{DOCS}', '{spec}')):results)) r"
        )
    rows = session.sql(" UNION ".join(parts)).collect()
    return "\n---\n".join(f"SOURCE: {r['URL']}\n{r['CHUNK']}" for r in rows)


def _llm_json(session, prompt, schema, max_tokens):
    row = session.sql(
        "SELECT AI_COMPLETE(model => ?, prompt => ?, response_format => PARSE_JSON(?), "
        "model_parameters => PARSE_JSON(?)) AS out",
        params=[LLM, prompt, json.dumps({"type": "json", "schema": schema}),
                json.dumps({"max_tokens": max_tokens, "temperature": 0})],
    ).collect()[0]
    out = row["OUT"]
    return json.loads(out) if isinstance(out, str) else out


def _deprecations(session, today):
    ctx = _docs_context(session, [
        "Cortex model deprecations",
        "model lifecycle legacy end-of-life EOL date table",
        "deprecated model recommended replacement alternative model",
        "AI_COMPLETE available models list",
    ], 10)
    schema = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "required": ["model", "eol_date", "replacement"],
        "properties": {k: {"type": "string"} for k in ["model", "legacy_date", "eol_date", "replacement", "source_url"]}}}}}
    prompt = (f"Today is {today}. From these Snowflake docs excerpts, list every Cortex model deprecation. "
              "Use lowercase model ids as passed to AI_COMPLETE. Dates YYYY-MM-DD, empty string if unknown. "
              "replacement = model the docs recommend, else the newest available model of the same vendor/size that is "
              "NOT itself deprecated; never the same model.\n\n" + ctx)
    return _llm_json(session, prompt, schema, 8000)["items"]


def _releases(session, today):
    feats = _docs_context(session, [
        "release notes general availability new feature", "public preview new feature",
        "new AI function Cortex preview", "feature releases recent"], 10)
    bundles = _docs_context(session, [
        "behavior change bundle disabled by default", "behavior change bundle enabled by default",
        "behavior change bundle history status"], 10)
    s = {"type": "string"}
    schema = {"type": "object", "required": ["features", "bundles", "bundle_changes"], "properties": {
        "features": {"type": "array", "items": {"type": "object", "required": ["name", "status", "source_url"], "properties": {
            "name": s, "status": s, "date": s, "is_ai": {"type": "boolean"}, "source_url": s}}},
        "bundles": {"type": "array", "items": {"type": "object", "properties": {"name": s, "status": s, "planned": s}}},
        "bundle_changes": {"type": "array", "items": {"type": "object", "properties": {"bundle": s, "title": s}}}}}
    prompt = (f"Today is {today}. Using ONLY these Snowflake docs excerpts, return the 10 most recent new features "
              "(status GA or Preview, date YYYY-MM-DD, is_ai for Cortex/AI features, source_url). Then the behavior change "
              "bundles not yet generally enabled plus the latest generally enabled one (name, status, planned), and up to "
              "5 key changes of the newest bundle (title under 12 words).\n\nFEATURES:\n" + feats + "\n\nBUNDLES:\n" + bundles)
    return _llm_json(session, prompt, schema, 6000)


def _norm(m):
    m = (m or "").lower().strip()
    return m.replace("claude-4-sonnet", "claude-sonnet-4").replace("claude-4-opus", "claude-opus-4")


def _status(d, today):
    e, l = d.get("eol_date") or "", d.get("legacy_date") or ""
    try:
        if e:
            days = (dt.date.fromisoformat(e) - today).days
            if days < 0: return "RETIRED", days
            if days <= 30: return "≤30 DAYS", days
            if days <= 90: return "≤90 DAYS", days
            if days <= 180: return "≤180 DAYS", days
            return "SCHEDULED", days
        if l:
            return ("LEGACY", None) if dt.date.fromisoformat(l) <= today else ("LEGACY SOON", None)
    except ValueError:
        pass
    return "DEPRECATED", None


def _pill(s, c=None):
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;background:{c or PILL.get(s, GRY)};'
            f'color:#fff;font-size:11px;font-weight:bold;white-space:nowrap">{E(s)}</span>')


def _td(content, extra=""):
    return f'<td style="{TD};{extra}">{content}</td>'


def _section(title, sub=""):
    sub_html = f'<div style="color:{GRY};font-size:12px;margin-top:2px">{sub}</div>' if sub else ""
    return f'<tr><td style="padding:28px 24px 8px"><div style="font-size:17px;font-weight:bold;color:#0F172A">{title}</div>{sub_html}</td></tr>'


def _card(inner):
    return ('<tr><td style="padding:0 24px"><table width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid #E2E8F0;border-radius:8px;border-collapse:separate;overflow:hidden">{inner}</table></td></tr>')


def _more(items, k, sep):
    s = sep.join(E(i) for i in items[:k])
    return s + (f' <span style="color:{GRY}">+{len(items) - k} more</span>' if len(items) > k else "")


def build_html(session):
    today = dt.date.today()
    account = session.sql("SELECT CURRENT_ACCOUNT_NAME() a").collect()[0]["A"]

    deps = {_norm(d["model"]): d for d in _deprecations(session, today)}
    rel = _releases(session, today)

    used = {}
    for r in session.sql(USAGE_SQL).collect():
        used.setdefault(_norm(r["MODEL"]), []).append(r)

    models = []
    for m, rs in used.items():
        d = deps.get(re.sub(r"\s*fine-tuned$", "", m))
        st, days = _status(d, today) if d else ("SUPPORTED", None)
        last = max(r["LAST_CALL"] for r in rs)
        models.append(dict(
            model=m, dep=d, status=st, days=days, last=last, calls=sum(r["CALLS"] for r in rs),
            users=sorted({r["USER_NAME"] for r in rs}),
            apps=sorted({(r["KIND"], r["OBJ"]) for r in rs if r["OBJ"]}),
            active=(today - last).days <= 30))
    risk = sorted([x for x in models if x["status"] != "SUPPORTED"],
                  key=lambda x: (x["status"] != "RETIRED", -x["calls"]))
    ok = sorted([x for x in models if x["status"] == "SUPPORTED"], key=lambda x: -x["calls"])

    # Hard-coded model names in procedures / functions / views
    hard = []
    if risk:
        names = sorted({re.sub(r"\s*fine-tuned$", "", x["model"]) for x in risk})
        names += ["claude-4-sonnet"] if "claude-sonnet-4" in names else []
        rx = "(" + "|".join(re.escape(n) for n in names) + r")(['\"])"
        hard = session.sql(f"""
            SELECT 'Procedure' t, procedure_catalog||'.'||procedure_schema||'.'||procedure_name obj, procedure_owner owner,
                   REGEXP_SUBSTR(LOWER(procedure_definition), ?, 1, 1, 'e', 1) m, last_altered::date la
            FROM SNOWFLAKE.ACCOUNT_USAGE.PROCEDURES WHERE deleted IS NULL AND REGEXP_LIKE(LOWER(procedure_definition), '.*' || ? || '.*', 's')
            UNION ALL
            SELECT 'Function', function_catalog||'.'||function_schema||'.'||function_name, function_owner,
                   REGEXP_SUBSTR(LOWER(function_definition), ?, 1, 1, 'e', 1), last_altered::date
            FROM SNOWFLAKE.ACCOUNT_USAGE.FUNCTIONS WHERE deleted IS NULL AND REGEXP_LIKE(LOWER(function_definition), '.*' || ? || '.*', 's')
            UNION ALL
            SELECT 'View', table_catalog||'.'||table_schema||'.'||table_name, table_owner,
                   REGEXP_SUBSTR(LOWER(view_definition), ?, 1, 1, 'e', 1), last_altered::date
            FROM SNOWFLAKE.ACCOUNT_USAGE.VIEWS WHERE deleted IS NULL AND REGEXP_LIKE(LOWER(view_definition), '.*' || ? || '.*', 's')
            ORDER BY la DESC""", params=[rx] * 6).collect()

    risk_users = sorted({u for x in risk for u in x["users"] if u != "(system)"})
    risk_agents = {o.split(".")[-1] for x in risk for k, o in x["apps"] if k in ("Agent", "Snowflake Intelligence")}

    # ---- 1. timeline chart ----
    months = {}
    for m, d in deps.items():
        key = d.get("eol_date") or d.get("legacy_date") or ""
        if re.match(r"\d{4}-\d{2}", key):
            months.setdefault(key[:7], []).append((m, m in used or f"{m} fine-tuned" in used))
    maxn = max([len(v) for v in months.values()] or [1])
    bars = ""
    for mo in sorted(months):
        items = sorted(months[mo], key=lambda i: not i[1])
        past = mo < today.isoformat()[:7]
        segs = "".join(
            f'<td style="background:{(RED if u else "#F3B0AA") if past else (AMB if u else "#F6D99A")};height:18px;border-right:2px solid #fff"></td>'
            for _, u in items)
        in_use = ", ".join(E(m) for m, u in items if u)
        label = dt.date.fromisoformat(mo + "-01").strftime("%b %Y")
        bars += (f'<tr><td style="width:64px;font-size:11px;color:{GRY};padding:4px 6px 4px 0;white-space:nowrap">{label}</td>'
                 f'<td style="padding:4px 0;width:45%"><table cellpadding="0" cellspacing="0" width="{max(6, round(len(items) / maxn * 100))}%"><tr>{segs}</tr></table></td>'
                 f'<td style="font-size:11px;padding:4px 0 4px 10px">{len(items)} model{"s" if len(items) > 1 else ""}'
                 f'{f"<br><b style=color:{RED}>in use: {in_use}</b>" if in_use else ""}</td></tr>')
    sw = lambda c: f'<span style="display:inline-block;width:10px;height:10px;background:{c}"></span>'
    chart = (f'<tr><td style="padding:14px 16px"><table width="100%" cellpadding="0" cellspacing="0">{bars}</table>'
             f'<div style="font-size:11px;color:{GRY};margin-top:10px">{sw(RED)} in use, passed &nbsp; {sw("#F3B0AA")} not used, passed &nbsp; '
             f'{sw(AMB)} in use, upcoming &nbsp; {sw("#F6D99A")} not used, upcoming<br>Date = end-of-life, or legacy date when EOL is not announced.</div></td></tr>')

    # ---- 2. action table ----
    def deadline(x):
        d = x["dep"]
        if d.get("eol_date"):
            when = f'{abs(x["days"])} days {"ago" if x["days"] < 0 else "left"}' if x["days"] is not None else ""
            return f'EOL {E(d["eol_date"])}<br><span style="color:{GRY};font-size:11px">{when}</span>'
        if d.get("legacy_date"):
            return f'Legacy since {E(d["legacy_date"])}<br><span style="color:{GRY};font-size:11px">EOL not announced</span>'
        return "Retired"

    def apps(x, k=3):
        names = sorted({o for _, o in x["apps"]}, key=lambda n: (n in ("AI_COMPLETE", "Cortex REST API"), n))
        return _more([n.replace(".", ".\u200b") for n in names], k, "<br>")

    act = "".join(f"<th {TH}>{h}</th>" for h in
                  ["Model", "Status", "Deadline", f"Users ({len(risk_users)})", "Agents / functions", "Last call", "Calls 180d", "Swap to"])
    act = f"<tr>{act}</tr>"
    for x in risk:
        swap = x["dep"].get("replacement") or "—"
        act += ("<tr>" + _td(f'<b style="{MONO}">{E(x["model"])}</b><br><span style="color:{GRY};font-size:11px">{E(account)}</span>')
                + _td(f'{_pill(x["status"])}<br><span style="font-size:11px;color:{GRN if x["active"] else GRY}">{"Active" if x["active"] else "Inactive (30d)"}</span>')
                + _td(deadline(x)) + _td(_more(x["users"], 4, ", ")) + _td(apps(x))
                + _td(str(x["last"]), "white-space:nowrap") + _td(f'{x["calls"]:,}', "text-align:right")
                + _td(f'<b style="{MONO};color:{GRN}">{E(swap)}</b>') + "</tr>")
    if not risk:
        act += f'<tr><td colspan="8" style="{TD};color:{GRN};font-weight:bold">All clear &mdash; no deprecated models in use.</td></tr>'

    # ---- 3. code swap ----
    cs = f"<tr><th {TH}>Where</th><th {TH}>Before</th><th {TH}>After</th></tr>"
    for x in risk:
        o, n = E(re.sub(r"\s*fine-tuned$", "", x["model"])), E(x["dep"].get("replacement") or "?")
        kinds = {k for k, _ in x["apps"]}
        pairs = []
        if "AI Function" in kinds: pairs.append(("AI function", f"AI_COMPLETE('{o}', …)", f"AI_COMPLETE('{n}', …)"))
        if kinds & {"Agent", "Snowflake Intelligence"}: pairs.append(("Agent spec", f"orchestration: {o}", f"orchestration: {n}"))
        if "REST API" in kinds: pairs.append(("REST API", f'"model": "{o}"', f'"model": "{n}"'))
        for w, b, a in pairs:
            cs += "<tr>" + _td(w) + _td(f'<span style="{MONO};color:{RED}">{b}</span>') + _td(f'<span style="{MONO};color:{GRN}">{a}</span>') + "</tr>"

    # ---- 4. hard-coded ----
    hc = "".join(f"<th {TH}>{h}</th>" for h in ["Object", "Type", "Model", "Owner role", "Last changed"])
    hc = f"<tr>{hc}</tr>"
    for h in hard:
        hc += ("<tr>" + _td(f'<span style="{MONO_WRAP}">{E(h["OBJ"]).replace(".", ".&#8203;")}</span>') + _td(h["T"]) + _td(f'<span style="{MONO}">{E(h["M"] or "")}</span>')
               + _td(E(h["OWNER"] or "")) + _td(str(h["LA"]), "white-space:nowrap") + "</tr>")
    if not hard:
        hc += f'<tr><td colspan="5" style="{TD};color:{GRN}">None found.</td></tr>'

    # ---- 5. all models ----
    allm = "".join(f"<th {TH}>{h}</th>" for h in ["Model", "Status", "Users", "Used by", "Last call", "Calls 180d"])
    allm = f"<tr>{allm}</tr>"
    for x in risk + ok:
        allm += ("<tr>" + _td(f'<span style="{MONO}">{E(x["model"])}</span>') + _td(_pill(x["status"])) + _td(len(x["users"]), "text-align:right")
                 + _td(E(", ".join(sorted({k for k, _ in x["apps"]}))), f"font-size:12px;color:{GRY}")
                 + _td(str(x["last"]), "white-space:nowrap") + _td(f'{x["calls"]:,}', "text-align:right") + "</tr>")

    # ---- 7. other deprecations ----
    others = sorted([(m, d) for m, d in deps.items() if m not in used and f"{m} fine-tuned" not in used],
                    key=lambda t: t[1].get("eol_date") or t[1].get("legacy_date") or "9999")
    nu = "".join(f"<th {TH}>{h}</th>" for h in ["Model", "Status", "Date", "Replacement"])
    nu = f"<tr>{nu}</tr>"
    for m, d in others:
        date = f'EOL {d["eol_date"]}' if d.get("eol_date") else (f'Legacy {d["legacy_date"]}' if d.get("legacy_date") else "Retired")
        nu += ("<tr>" + _td(f'<span style="{MONO}">{E(m)}</span>') + _td(_pill(_status(d, today)[0])) + _td(E(date), "white-space:nowrap")
               + _td(f'<span style="{MONO}">{E(d.get("replacement") or "")}</span>') + "</tr>")

    # ---- 8/9. features + bundles ----
    fr = ""
    for f in sorted(rel.get("features", []), key=lambda f: f.get("date") or "", reverse=True):
        ga = "GA" if (f.get("status") or "").upper().startswith("G") else "PREVIEW"
        tags = _pill(ga, GRN if ga == "GA" else BLU) + (" " + _pill("AI", NAVY) if f.get("is_ai") else "")
        fr += ("<tr>" + _td(E(f.get("date") or ""), "white-space:nowrap") + _td(tags)
               + _td(f'<a href="{E(f.get("source_url") or "https://docs.snowflake.com/en/release-notes/new-features")}" style="{LINK}">{E(f["name"])}</a>') + "</tr>")
    br = ""
    for b in rel.get("bundles", []):
        chg = " &middot; ".join(E(c.get("title") or "") for c in rel.get("bundle_changes", []) if c.get("bundle") == b.get("name"))
        br += ("<tr>" + _td(f'<a href="https://docs.snowflake.com/en/release-notes/bcr-bundles/{E(b.get("name") or "")}_bundle" style="{LINK}">{E(b.get("name") or "")}</a>')
               + _td(E(b.get("status") or "")) + _td(chg or E(b.get("planned") or ""), "font-size:12px") + "</tr>")

    # ---- header, tiles, banner ----
    tiles = "".join(
        f'<td width="20%" style="padding:3px"><table width="100%" cellpadding="0" cellspacing="0" style="background:#fff;border:1px solid #E2E8F0;border-top:4px solid {c};border-radius:8px">'
        f'<tr><td style="padding:12px 6px;text-align:center"><div style="font-size:24px;font-weight:bold;color:{c}">{v}</div>'
        f'<div style="font-size:11px;color:{GRY};text-transform:uppercase">{k}</div></td></tr></table></td>'
        for k, v, c in [("Models in use", len(models), NAVY), ("At risk", len(risk), RED), ("Users affected", len(risk_users), AMB),
                        ("Agents affected", len(risk_agents), AMB), ("Code to fix", len(hard), RED)])
    if risk:
        retired = [x["model"] for x in risk if x["status"] == "RETIRED"]
        busiest = [x["model"] for x in sorted(risk, key=lambda x: -x["calls"]) if x["status"] != "RETIRED"][:2]
        msg = f"<b>Do this week:</b> {len(risk)} models in use are deprecated. "
        if retired: msg += f"<b>{E(', '.join(retired))}</b> already reached end-of-life &mdash; swap now. "
        if busiest: msg += f"<b>{E(' and '.join(busiest))}</b> have the most usage &mdash; plan the swap next. "
        if hard: msg += f"Fix the {len(hard)} hard-coded objects in section 4."
        banner = (f'<tr><td style="padding:16px 24px 0"><table width="100%" cellpadding="0" cellspacing="0" style="background:#FDECEA;border-left:4px solid {RED};border-radius:6px">'
                  f'<tr><td style="padding:12px 14px;font-size:13px;color:#5F1C16">{msg}</td></tr></table></td></tr>')
    else:
        banner = (f'<tr><td style="padding:16px 24px 0"><table width="100%" cellpadding="0" cellspacing="0" style="background:#E6F4EA;border-left:4px solid {GRN};border-radius:6px">'
                  f'<tr><td style="padding:12px 14px;font-size:13px;color:#0D3D1C"><b>All clear:</b> no deprecated models are used in this account.</td></tr></table></td></tr>')

    logo = ('<table cellpadding="0" cellspacing="0"><tr><td style="font-size:26px;color:#fff;line-height:1;padding-right:8px">&#10052;</td>'
            '<td style="font-size:22px;font-weight:bold;color:#fff;letter-spacing:.5px">snowflake</td></tr></table>')
    sql_box = (f'<tr><td style="padding:0 24px"><pre style="background:#0F172A;color:#E2E8F0;padding:14px;border-radius:8px;'
               f'font-family:Menlo,Consolas,monospace;font-size:12px;white-space:pre-wrap;margin:0">{E(DETAIL_SQL)}</pre></td></tr>')

    html = f"""<div style="margin:0;background:#EEF2F6;font-family:Arial,Helvetica,sans-serif;color:#1E293B">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#EEF2F6"><tr><td align="center" style="padding:20px 8px">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:920px;background:#FFFFFF;border-radius:10px;overflow:hidden">
<tr><td style="background:{NAVY};background-image:linear-gradient(120deg,{NAVY},{SF});padding:22px 24px">{logo}
<div style="color:#fff;font-size:20px;font-weight:bold;margin-top:12px">AI Release Management</div>
<div style="color:#DDF3FB;font-size:13px;margin-top:2px">Account {E(account)} &middot; Week of {today:%b %d, %Y} &middot; Last 180 days of usage</div></td></tr>
<tr><td style="padding:18px 20px 0"><table width="100%" cellpadding="0" cellspacing="0"><tr>{tiles}</tr></table></td></tr>
{banner}
{_section('1 &nbsp;Deprecation timeline', 'Every announced Cortex model retirement. Red / amber = used in this account.')}
{_card(chart)}
{_section('2 &nbsp;Action required &mdash; models in use that are deprecated', 'Sorted by urgency. Contact the users listed; swap to the model in green.')}
{_card(act)}
{_section('3 &nbsp;Code swap') + _card(cs) if risk else ''}
{_section(f'4 &nbsp;Hard-coded model names to fix ({len(hard)})', 'Procedures, functions and views whose definition contains an at-risk model.')}
{_card(hc)}
{_section(f'5 &nbsp;All models used in this account ({len(models)})')}
{_card(allm)}
{_section('6 &nbsp;Full detail &mdash; copy, paste, run', 'Lists every user, agent and function for one model.')}
{sql_box}
<tr><td style="padding:24px 24px 0"><div style="border-top:2px solid #E2E8F0"></div></td></tr>
{_section(f'7 &nbsp;Other deprecations (not used here) ({len(others)})', 'No action needed. Avoid adopting these.')}
{_card(nu)}
{_section('8 &nbsp;New features &mdash; GA and Preview', f'<a href="https://docs.snowflake.com/en/release-notes/new-features" style="color:#0B6FA4">All release notes</a>')}
{_card(fr)}
{_section('9 &nbsp;Behavior change bundles', f'<a href="https://docs.snowflake.com/en/release-notes/behavior-changes" style="color:#0B6FA4">Bundle history and test guide</a>')}
{_card(br)}
<tr><td style="padding:24px;font-size:11px;color:{GRY};line-height:1.6">Sources: Snowflake Documentation (Marketplace) &middot; SNOWFLAKE.ACCOUNT_USAGE (up to ~3h latency).<br>
Legacy = only accounts that already used the model may keep calling it until end-of-life. &ldquo;(system)&rdquo; = calls without a user (tasks, services).<br>
Generated weekly by AI_MODEL_WATCH.CORE.SEND_REPORT.</td></tr>
</table></td></tr></table></div>"""
    subject = (f"AI Release Management - {account} - {len(risk)} models at risk" if risk
               else f"AI Release Management - {account} - All clear")
    return subject, html


def main(session, integration: str, recipients: str, send: bool) -> str:
    subject, html = build_html(session)
    if not send:
        return html
    session.sql("CALL SYSTEM$SEND_EMAIL(?, ?, ?, ?, 'text/html')",
                params=[integration, recipients, subject, html]).collect()
    return f"Sent: {subject}"
