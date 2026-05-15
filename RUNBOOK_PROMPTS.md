# OpenClaw Weather Bot — Build Runbook (Copy/Paste Prompts)

This is a **literal sequence of prompts** to paste into your OpenClaw chat (Telegram, TUI, or web UI) to scaffold a complete weather-bot operation modeled after **US Weather Warriors Delmarva**.

> Each prompt is wrapped in a fenced block so you can copy it cleanly. Run them **in order**. Wait for OpenClaw to finish each step before sending the next. Replace anything in `«angle brackets»` with your actual values before sending.

> Pair this with [`SETUP_GUIDE.md`](./SETUP_GUIDE.md), which covers the install/account-creation steps. This file is just the prompts.

---

## How to use this runbook

1. **Finish §3 through §7 of `SETUP_GUIDE.md`** first (install OpenClaw, connect Telegram, Gmail, optionally Facebook). You need a working OpenClaw chat session before any of these prompts will work.
2. Open a chat with your OpenClaw bot (Telegram DM is what we use).
3. Send **Prompt 0** to verify the bot is alive.
4. Walk through prompts **1 → 12** in order.
5. After each one, OpenClaw will create files, write code, or schedule cron jobs. Read what it did. Push back if anything's wrong.
6. Where prompts say "TEST IT", actually run the test before moving on.

---

## Prompt 0 — Sanity check

```
Hi. Confirm you can read my workspace at ~/.openclaw/workspace and that
tools.exec.ask is set to "off". Then show me your current model and the
list of cron jobs you can see.
```

**Expected:** Bot confirms workspace, says ask=off, names the model, lists cron jobs (probably empty).

---

## Prompt 1 — Set persistent identity for the project

```
I want to build a public-facing AI weather operation called «Your Brand
Name» that covers «Your Region» (cities: «City1, City2, City3»; states:
«ST,ST»; NWS forecast offices: «PHI,AKQ»; timezone: «America/New_York»).

Please:
1. Update SOUL.md so your tone is calm, competent, and weather-savvy.
2. Update USER.md with my brand name and region.
3. Add a new MEMORY.md entry summarizing the goal of this project so
   future sessions remember the context.
4. Show me the diffs before applying.
```

**Why:** Anchors every future session in the project's identity so prompts stay short.

---

## Prompt 2 — Create the project skeleton

```
Create a Python project at ~/.openclaw/workspace/weather-agent with:

- A virtualenv at .venv (Python 3.11+)
- requirements.txt with: requests, python-dateutil, python-dotenv,
  beautifulsoup4, pillow, imapclient, geojson, shapely
- src/weather/ as the package directory
- scripts/ for CLI entry points
- state/ for runtime JSON
- output/ for generated drafts
- logs/ for runtime logs
- A .env.example with all the variables from the SETUP_GUIDE.md
  template (Telegram, Gmail, Facebook, region settings)
- A .gitignore that excludes .env, .venv/, output/, state/, logs/, __pycache__
- A README.md that links back to SETUP_GUIDE.md and RUNBOOK_PROMPTS.md

Activate the venv and install requirements. Confirm the directory tree
when done.
```

**TEST IT:** Bot should print a clean `tree -L 2` of the new project.

---

## Prompt 3 — Build the data clients

```
In ~/.openclaw/workspace/weather-agent/src/weather/, create these
modules with a consistent interface (each exposes a small, well-named
function and returns plain dicts/lists):

1. nws_client.py — get_forecast(lat, lon), get_active_alerts(state_code),
   get_office_afd(office_code). Always send a User-Agent header.
2. spc_client.py — get_day1_outlook(), get_day2_outlook(),
   get_active_mds(). Parse the SPC GeoJSON outlooks.
3. wpc_client.py — get_excessive_rainfall_outlook().
4. geo.py — point_in_polygon(lat, lon, geojson_feature) and a helper
   load_region_polygon() that reads a GeoJSON file at
   data/region_polygon.geojson (create a placeholder file with the
   counties for «Your Region»).
5. approval_store.py — file-locked JSON store with new_pending(kind,
   draft_path, ttl_hours), get(approval_id), mark_approved(id, by),
   mark_rejected(id, by), list_pending(kind=None). State file at
   state/approvals.json.
6. telegram_client.py — send_message(chat_id, text), send_photo(...).
   Read TELEGRAM_BOT_TOKEN from .env.
7. email_client.py — send(subject, body, to, attachments=None) using
   Gmail SMTP, and poll_unread(filter_subject=None) using IMAP.
8. facebook_publisher.py — publish_post(text, image_path=None) hitting
   the Graph API with FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN.

Write small unit tests for approval_store.py and geo.py under tests/.
Run the tests and show me the results.
```

**TEST IT:** All tests should pass before continuing.

---

## Prompt 4 — Install the Telegram approval router hook

```
Create an OpenClaw hook at
~/.openclaw/workspace/hooks/weather-approval-router/ with HOOK.md and
handler.js. The handler should match Telegram messages of exact form
"APPROVE <id>" or "REJECT <id>" where the id starts with one of these
prefixes: dfa_, sva_, mca_, gca_, sra_, aea_, asa_.

When matched, run scripts/handle_routed_telegram_approval.py inside
the weather-agent venv with --text, --sender-id, --chat-id, and verify
the sender ID is in TELEGRAM_APPROVER_IDS before changing approval
state. Append a diagnostic line to ~/.openclaw/logs/weather-approval-router.log.

Also create scripts/handle_routed_telegram_approval.py inside the
weather-agent project. It should look up the approval ID, mark it
approved, and dispatch to the matching publisher script.

Restart the gateway when done.
```

**TEST IT:** Send `APPROVE dfa_test123` to your Telegram bot. Check `~/.openclaw/logs/weather-approval-router.log` to confirm the hook saw the message (it'll log `matched=true, handled=false` because dfa_test123 doesn't exist — that's expected).

---

## Prompt 5 — Build the Daily Forecast bot

```
Build the Daily Forecast bot for «Your Region». Create these scripts
under weather-agent/scripts/:

1. daily_forecast.py [--phase morning|afternoon] — pulls forecasts for
   each WX_FORECAST_POINTS city, alerts for each WX_STATE_CODES, AFDs
   from each WX_NWS_OFFICES, calls the LLM to draft a Facebook post in
   our brand voice, saves draft to output/YYYY-MM-DD/final_post.md.
   Afternoon phase reads the morning snapshot and focuses on changes.

2. request_daily_forecast_approval.py [--latest] — reads the latest
   draft, registers a new approval (prefix dfa_), sends Telegram + email
   approval requests with the ID baked in.

3. check_daily_forecast_approval.py [--send-notifications] — checks
   pending dfa_ approvals, expires stale ones, and on first valid
   approval calls publish_approved_daily_forecast.py.

4. publish_approved_daily_forecast.py --approval-id <id> — posts the
   approved draft to Facebook, sends a success/failure notification.

Then add four cron jobs (isolated sessions, America/New_York timezone,
default model, payload kind=agentTurn):

- "Daily Forecast Morning Generator" at 06:30 daily
- "Daily Forecast Morning Approval Request" at 06:40 daily
- "Daily Forecast Afternoon Generator" at 15:00 daily
- "Daily Forecast Afternoon Approval Request" at 15:10 daily
- "Daily Forecast Approval Checker" every 15 minutes

Show me the cron list when done.
```

**TEST IT:**
```
Manually run daily_forecast.py for me right now and show the resulting
draft. Don't request approval and don't post — just generate.
```

---

## Prompt 6 — Build the Severe Weather bot

```
Build the Severe Weather bot. Create:

1. check_spc_changes.py — pulls SPC Day 1/2 outlooks and active MDs,
   intersects them with our region polygon, compares against
   state/severe_last_seen.json. Only escalates if categorical risk
   changed (e.g. None→MRGL, MRGL→SLGT) or a new MD overlaps our region.

2. severe_weather_monitor.py — when escalation detected, drafts an
   update post (calm, factual, no hype) and registers an sva_ approval.

3. check_severe_weather_approval.py [--send-notifications]
4. publish_approved_severe_weather.py --approval-id <id>

Cron jobs:
- "Severe Weather SPC Checker" at 10:00, 13:00, 16:00, 19:00 daily
- "Severe Weather Approval Checker" every 15 minutes

Hard rule in the prompt for the LLM: never use words like "outbreak",
"historic", "catastrophic", or "life-threatening" unless those words
appear verbatim in the official NWS/SPC text.
```

---

## Prompt 7 — Build the Alert Explainer bot

```
Build the Alert Explainer bot. It translates raw NWS warnings into
plain English with a county map.

Create:

1. alert_explainer.py — takes one NWS alert feature, generates a
   Facebook draft and a Telegram preview, and an alert map PNG.
2. run_alert_explainer.py — polls api.weather.gov/alerts/active for
   our states, dedups against state/alert_explainer_seen.json, and
   for each new explainable alert calls alert_explainer.py and
   request_alert_explainer_approval.py (prefix aea_).
3. check_alert_explainer_approval.py [--send-notifications]
4. publish_approved_alert_explainer.py --approval-id <id>
5. generate_alert_map.py — draws affected counties on a basemap.

Cron jobs:
- "Alert Explainer Runner" every 15 minutes
- "Alert Explainer Approval Checker" every 15 minutes

Always include a closer in every warning post: "Have multiple ways to
receive warnings — NOAA Weather Radio, Wireless Emergency Alerts, and
local media."
```

---

## Prompt 8 — Build the Storm Reports bot

```
Build the Storm Reports bot for post-event recaps. Create:

1. storm_reports_monitor.py — pulls today's filtered LSR CSV from SPC,
   filters to our region by FIPS or polygon, groups by event type
   (tornado, hail, wind, flooding, marine), drafts a recap.
2. request_storm_reports_approval.py (prefix sra_)
3. check_storm_reports_approval.py [--send-notifications]
4. publish_approved_storm_reports.py --approval-id <id>

Cron jobs:
- "Storm Reports Generator" at 22:00 daily
- "Storm Reports Approval Checker" every 15 minutes
```

---

## Prompt 9 — Build the MarineCast bot (skip if inland)

```
Build the MarineCast bot for «Your Marine Zones» (NWS marine zone
codes: «AMZ###,AMZ###»). Create:

1. marinecast.py [--daily] — pulls marine forecasts and small craft
   advisories, drafts a boater-focused post.
2. request_marinecast_approval.py (prefix mca_)
3. check_marinecast_approval.py [--send-notifications]
4. publish_approved_marinecast.py --approval-id <id>

Cron jobs:
- "MarineCast Daily Generator" at 05:00 daily
- "MarineCast Approval Checker" every 15 minutes
```

If your region has no coastline, tell OpenClaw: *"Skip the MarineCast
bot — we are inland."*

---

## Prompt 10 — Build the GrowCast bot

```
Build the GrowCast bot — seasonal gardening / lawn / small-farm
guidance. Create:

1. growcast.py [--daily --public | --weekly --private --send-email] —
   public daily Facebook draft and a private weekly briefing emailed
   to GROWCAST_PRIVATE_RECIPIENTS.
2. request_growcast_approval.py (prefix gca_)
3. check_growcast_approval.py [--send-notifications]
4. publish_approved_growcast.py --approval-id <id>

Cron jobs (only run April through October):
- "GrowCast Daily Generator" at 07:00 daily, months 4-10
- "GrowCast Approval Request" at 07:15 daily, months 4-10
- "GrowCast Weekly Private Briefing" at 08:00 every Sunday
- "GrowCast Approval Checker" every 15 minutes
```

---

## Prompt 11 — Build the private internal bots

```
Build two PRIVATE bots that never publish publicly. They only send to
me and my listed forecaster team.

1. forecaster_briefing.py [--send-all] — daily technical briefing:
   instability, shear, lapse rates, moisture, storm mode, limiting
   factors. Email to FORECASTER_BRIEFING_EMAIL_RECIPIENTS. No Facebook.
   Cron: "Forecaster Briefing" at 06:45 daily.

2. chase_target_advisor.py [--send-all] — recommends primary +
   secondary chase targets for severe-weather days. ONLY sends if
   severe potential is at least Marginal AND chase safety checks
   pass. Email to CHASE_TARGET_EMAIL_RECIPIENTS. No Facebook.
   Cron: "Chase Target Advisor Morning" at 07:00 daily; and
         "Chase Target Advisor Hourly" at 10-21 hours daily.

For both, the cron prompt to the LLM must explicitly forbid
publishing or Telegram broadcasts.
```

---

## Prompt 12 — Build the Sounding Email Analyst (optional)

```
Build the Sounding Email Analyst. Authorized senders email a Skew-T
or hodograph image to «yourbrand-weatherbot@gmail.com» and the bot
emails back a structured severe-weather sounding analysis.

Create:

1. poll_sounding_email_requests.py — polls Gmail IMAP for unread
   messages from senders in SOUNDING_EMAIL_ALLOWED_SENDERS only.
   For each, downloads attached images, writes a request JSON to
   state/sounding_requests/, prints REQUEST_JSON=<path> lines.
2. send_sounding_email_response.py --request <json> --analysis <md>
   — emails the analysis back to the original sender.

Cron job:
- "Sounding Email Analyst Watcher" every 10 minutes, isolated session,
  with toolsAllow=["exec","read","write","image"], and a prompt that
  says: for each REQUEST_JSON line, read the JSON, analyze each image
  using the model-sounding-severe-analyst skill (or equivalent prompt),
  write analysis.md, and call send_sounding_email_response.py.
  Hard rule: never publish, never Telegram, never edit code.
```

---

## Prompt 13 — Final wiring and verification

```
Now do a full audit of what we built. Show me:

1. The output of: openclaw config get tools.exec
   (must be ask=off, security=full)
2. The full cron list with names, schedules, and timezones.
   Confirm no checker runs more frequently than every 15 minutes.
3. The contents of ~/.openclaw/workspace/weather-agent/.env.example
4. A tree of weather-agent/ to depth 2.
5. A summary of every approval-ID prefix in use and which bot owns it.

Then propose three things you would tighten or improve before going
to production. Wait for my go-ahead before changing anything.
```

---

## Prompt 14 — Daily ops tips

Copy these and use whenever you need them:

**Re-run something manually:**
```
Run the daily forecast generator now (don't request approval, just
generate). Show me the draft.
```

**Disable a noisy bot temporarily:**
```
Disable the «GrowCast Daily Generator» cron job. Confirm it's
disabled. I'll re-enable it when I'm ready.
```

**Force a re-publish of an existing approved draft:**
```
Re-publish the approved daily forecast for 2026-05-15 to Facebook.
Use the existing approval ID — don't request a new one.
```

**Clean up old state:**
```
Delete approval entries older than 7 days from
state/approvals.json. Show me what you removed.
```

**Investigate a missed alert:**
```
There was a tornado warning in «County Name» around «time» yesterday.
Did the Alert Explainer process it? Check state/alert_explainer_seen.json
and ~/.openclaw/logs/. Tell me what happened.
```

---

## What good looks like

After all 14 prompts, you should have:

- ✅ ~20 cron jobs, all on 15-minute or longer cadences
- ✅ One approval router hook handling 7 ID prefixes
- ✅ A `weather-agent/` Python project with one venv, ~25–30 scripts, and a clean tests/ directory
- ✅ Telegram + email + (optional) Facebook all wired
- ✅ Nothing posts publicly without an `APPROVE <id>` from your verified Telegram ID

If something's missing or broken, **ask OpenClaw to fix it conversationally** — that's the whole point of building it this way.

Stay safe. ⛈️
