# OpenClaw Weather Bot — Build Runbook (Copy/Paste Prompts)

This is a **literal sequence of prompts** to paste into your OpenClaw chat (Telegram, TUI, or web UI) to scaffold a complete weather-bot operation modeled after **US Weather Warriors Delmarva**.

> Each prompt is wrapped in a fenced block so you can copy it cleanly. Run them **in order**. Wait for OpenClaw to finish each step before sending the next. Replace anything in `«angle brackets»` with your actual values before sending.

> Pair this with [`SETUP_GUIDE.md`](./SETUP_GUIDE.md), which covers the install/account-creation steps. This file is just the prompts.

---

## How to use this runbook

1. **Finish §3 through §7 of `SETUP_GUIDE.md`** first (install OpenClaw, connect Telegram, Gmail, optionally Facebook). You need a working OpenClaw chat session before any of these prompts will work.
2. Open a chat with your OpenClaw bot (Telegram DM is what we use).
3. Send **Prompt 0** to verify the bot is alive.
4. Walk through prompts **1 → 16** in order.
5. After each one, OpenClaw will create files, write code, or schedule cron jobs. Read what it did. Push back if anything's wrong.
6. Where prompts say "TEST IT", actually run the test before moving on.

**Important scheduling note (read before prompt 5):** approval
checkers and email pollers should run as **systemd user timers**, not
OpenClaw cron jobs. OpenClaw cron `agentTurn` hard-codes
`tools.exec.security` to allowlist, which generates a Telegram
approval prompt for every script call. systemd avoids that. The
prompts below say "as a systemd timer" for checkers and "as an
OpenClaw cron" for LLM-driven generators — that split matters. See
`SETUP_GUIDE.md` §13.1 for the unit-file template.

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
prefixes: dfa_, sva_, mca_, gca_, sra_, aea_, asa_, twa_, ewa_.

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

Then add five jobs (use America/New_York timezone) split across
schedulers per `SETUP_GUIDE.md` §13.1:

**OpenClaw cron** (isolated session, default model, payload
kind=agentTurn, payload.toolsAllow=["exec","read"]):
- "Daily Forecast Morning Generator + Approval Request" at 06:30 daily
- "Daily Forecast Afternoon Generator + Approval Request" at 15:00 daily

(Each cron's message runs `daily_forecast.py --phase <morning|afternoon>`
*then* `request_daily_forecast_approval.py --latest` in one shell
invocation, so we don't spawn the approval-request as its own LLM
turn.)

**systemd user timer** (cadence every 15 min, install per
`SETUP_GUIDE.md` §13.1 template):
- `weather-daily-forecast-approval-checker.timer` running
  `check_daily_forecast_approval.py --send-notifications --verbose`
  (the script itself self-gates to 06:30–18:00 local time).

Show me the OpenClaw cron list AND `systemctl --user list-timers
'weather-*'` when done.
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

Cron / timer split:
- **OpenClaw cron** (LLM-driven, toolsAllow=["exec","read"]):
  "Severe Weather SPC Checker" at 10:00, 13:00, 16:00, 19:00 daily.
- **systemd timer**: `weather-severe-weather-approval-checker.timer`
  every 15 min.

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

Cron / timer split:
- **OpenClaw cron** (LLM-driven, toolsAllow=["exec","read","write"]):
  "Alert Explainer Runner" every 15 min.
- **systemd timer**:
  `weather-alert-explainer-approval-checker.timer` every 15 min.

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

Cron / timer split:
- **OpenClaw cron**: "Storm Reports Generator" at 22:00 daily.
- **systemd timer**: `weather-storm-reports-approval-checker.timer`
  every 15 min.
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

Cron / timer split:
- **OpenClaw cron**: "MarineCast Daily Generator + Approval Request"
  at 05:00 daily (the generator and request-approval run in one shell
  invocation).
- **systemd timer**: `weather-marinecast-approval-checker.timer`
  every 15 min.
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

Cron / timer split:
- **OpenClaw cron** (only run April through October):
  - "GrowCast Daily Generator + Approval Request" at 07:00 daily,
    months 4-10.
  - "GrowCast Weekly Private Briefing" at 08:00 every Sunday.
- **systemd timer**: `weather-growcast-approval-checker.timer`
  every 15 min.
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

Cron job (read-gated split per `SETUP_GUIDE.md` §13.10):
- **systemd timer**: `weather-sounding-email-poll.timer` every 10 min
  runs `poll_sounding_email_requests.py`, writing
  `state/sounding_pending.json`.
- **OpenClaw cron**: "Sounding Email Analyst Watcher" every 15 minutes,
  isolated session, with toolsAllow=["exec","read","write","image"], and
  a prompt that says: read `state/sounding_pending.json`; if
  `count==0` reply `STILL_NOTHING_TO_DO` and exit; otherwise for each
  pending request analyze each image using the
  model-sounding-severe-analyst skill (or equivalent prompt), write
  analysis.md, and call send_sounding_email_response.py.
  Hard rule: never publish, never Telegram, never edit code.
```

---

## Prompt 13 — Add the LLM writer + deterministic safety net

```
For every public bot we built (daily_forecast, severe_weather,
alert_explainer, storm_reports, marinecast, growcast public draft) and
for the forecaster_briefing, add an LLM writer module with a
deterministic safety-net fallback per SETUP_GUIDE.md §13.3.

For each bot:

1. Create src/weather/<bot>_writer.py with:
   - A dataclass exposing model=None (defer to gateway default).
   - build_prompt(source_bundle) -> str.
   - write_post(source_bundle, fallback_callable) -> (text, llm_used,
     fallback_reason). Calls `openclaw capability model run --prompt
     <file> --gateway --json`. Falls back to the deterministic
     generator on any subprocess error, timeout, non-OK envelope, or
     empty outputs[0].text.

2. Wire the writer into the bot's generator script. Save
   <bot>_llm_prompt.txt and <bot>_llm_meta.json next to the normal
   output. Add a --no-llm CLI flag that forces deterministic mode.

3. Add scripts/test_<bot>_writer.py covering: prompt-contents check,
   success path, subprocess-error fallback, non-OK-envelope fallback.
   Use an injectable cli_runner so the LLM call is mocked.

4. For the forecaster_briefing prompt: no emojis, no hashtags, no
   sign-off; allow technical shorthand (CAPE/SRH/PWAT/LCL); explicit
   rule to say "unavailable from current source data" rather than
   invent values; 120s timeout. For public bots: target word count,
   one allowed header emoji, hashtag whitelist, brand sign-off,
   standard public closer, 90s timeout.

5. Hard prompt rules across all bots: no fabrication of CAPE / shear /
   lapse rates / rainfall / dewpoints / frost dates / soil temps /
   hazard categories; no softening of NWS/SPC wording; SPC
   categorical labels (Marginal/Slight/Enhanced/Moderate/High/PDS)
   reproduced verbatim.

Run all writer smoke tests when done and show me the results.
```

**TEST IT:** Generate one post each way and diff:
```
Run daily_forecast.py once with --no-llm (deterministic) and once
without (LLM). Show me a diff of the two final_post outputs.
```

---

## Prompt 14 — Add the approval-request idempotency guard

```
Add the idempotency guard from SETUP_GUIDE.md §13.4 to every
--request-approval code path.

1. Create src/weather/approval_idempotency.py with
   find_existing_pending_approval(store, forecast_date, dry_run=False)
   matching the helper in the setup guide.

2. In every request_*_approval.py and any inline-request path
   (e.g. marinecast.py --request-approval), call the guard right
   before store.create_approval(...). On hit: print
   REUSED_EXISTING_APPROVAL_ID=<id>, print STATUS=<status>, and exit
   0 without creating a duplicate or sending Telegram + email
   notifications.

3. Add a test that runs --request-approval twice for the same date
   and verifies the second call reuses the first approval ID and
   sends no notifications.

4. Also update the publisher dedup: save LLM writer output to
   <basename>_llm.md (not <basename>.md) so a same-day re-post never
   collides with the publisher's mark_post_attempt path-based guard
   per §13.5.

Run the new tests when done.
```

---

## Prompt 15 — (Optional) Add the second publish target: your own website

Skip this prompt if you don't have a website to publish to.

```
Add a second publish target alongside Facebook per SETUP_GUIDE.md
§13.6.

1. Create src/weather/website_client.py exposing WebsiteClient,
   excerpt_from_markdown, record_website_result,
   already_posted_to_website. POSTs to WEBSITE_BASE_URL +
   /api/openclaw/publish with HMAC-SHA256 auth (X-USWW-Api-Key,
   X-USWW-Timestamp, X-USWW-Signature: sha256=<hex>) over
   timestamp + "." + rawBody. Honors WEBSITE_DISABLED=1 kill switch.

2. Create scripts/publish_to_website_<bot>.py for each in-scope bot
   (daily_forecast, marinecast, growcast public draft only,
   severe_weather, alert_explainer). Storm Reports, sounding
   analyst, forecaster briefing, chase target advisor, and the
   GrowCast private weekly briefing are OUT OF SCOPE — do not wire
   website publishers for those.

3. Modify each check_<bot>_approval.py to call
   publish_to_website_<bot>.py AFTER the Facebook publish, inside a
   try/except that does NOT block the Facebook publish on failure.
   Use the local idempotency guard (skip if approval record's
   website_status == "posted"). Server should also dedupe on
   approvalId as backstop.

4. Approval records gain: website_status
   (posted/post_failed/disabled), website_post_id,
   website_public_url, website_published_at, website_error,
   website_status_code.

5. Add a test that simulates a website failure and verifies the
   Facebook publish status is unaffected.

Run the new tests when done.
```

---

## Prompt 16 — (Optional) Per-customer paid workflow: Event Weather Advisor

Skip this prompt if you're not running a paid customer offering.

```
Build the Event Weather Advisor per SETUP_GUIDE.md §13.7 — a
per-event weather advisory for paying customers (outdoor weddings,
concerts, festivals, sports).

Create under weather-agent/scripts/:

1. event_weather_intake.py — register a customer event (event_id
   prefix ewa_, datetime, lat/lon, venue, customer contact, internal
   notes). Persist to state/event_weather_requests.json.

2. event_weather_prepare_update.py --event-id ewa_<id> —
   deterministic Python that pulls NWS active alerts + daily/hourly
   forecast for the event point, AFD context, SPC categorical risk
   (only when event ≤ 3 days out), WPC excessive rainfall, and
   climatology (NOAA normals + 30-yr historical analog + CPC monthly
   outlooks) for far-out events. Computes a risk summary (Overall +
   Rain / Thunderstorm / Severe / Wind / Heat / Cold / Flooding /
   Setup-Teardown). Writes source_bundle_*.json, risk_summary_*.json,
   and an LLM prompt packet event_weather_llm_prompt_*.md under
   output/event_weather/<event_id>/. Tags the bundle with
   data_strategy = climate_only when event > NWS forecast window.

3. event_weather_send_email.py --event-id ewa_<id>
   [--send-internal | --send-customer]
   --internal-review-file <path> --message-file <path> —
   operator-gated email send. Internal review goes to
   EVENT_WEATHER_INTERNAL_RECIPIENTS; customer email goes to the
   registered customer contact only. NEVER auto-sends.

4. event_weather_due_updates.py — (optional, no LLM) prints which
   events are due for a refresh based on their cadence and the
   timestamp of their last update. Use this from a systemd timer if
   you want a recurring reminder loop.

5. event_weather_status.py — readonly inspector.

Hard rules for the LLM prompt (encode in
prompts/event_weather_llm_generation_instructions.md):
- Dual-output document separated by the literal marker
  <<<CUSTOMER_UPDATE_BELOW>>>.
- NEVER recommend cancellation, postponement, or evacuation unless
  risk.overall == High OR an active severe/flood warning is in the
  source bundle alerts.
- NEVER fabricate forecast values; say "unavailable from current
  source data" instead.
- NEVER present climatology as a forecast. Use "historically," "on
  average," "the CPC monthly outlook leans toward."
- If data_strategy == climate_only, state that plainly in the
  customer email; confidence stays Low.
- Customer email closes with a line directing the customer to monitor
  official NWS warnings independently, then the brand sign-off.
- NEVER posts to Facebook or the website.

No cron job for this bot — it is operator-driven. Optionally install
event_weather_due_updates.py as a systemd timer that just logs
"events due" without sending anything.
```

---

## Prompt 16.5 — (Optional) Tropical Watch Bot

Skip this prompt if your region is landlocked or otherwise won't see tropical impacts.

```
Build the Tropical Watch Bot per SETUP_GUIDE.md §10.10. It is a
pure-Python NHC monitor (no LLM in the monitor loop — LLM only enters
at approval-message render time).

Create under weather-agent/:

1. src/weather/tropical_bot.py — TropicalWatchBot.run(dry_run,
   force_notify, update_state) that:
   - Pulls NHC Tropical Weather Outlooks (Atlantic + East Pacific).
   - Pulls active-storm advisories.
   - Filters for region relevance (forecast cone intersects our
     region polygon, TWO highlights a system threatening our coast).
   - Dedups against state/tropical_seen.json by
     system_id + advisory_number.
   - Returns a result object with should_notify,
     new_systems_count, active_storms_count,
     skipped_duplicate_count.

2. scripts/tropical_watch.py [--dry-run] [--send-telegram]
   [--force-notify] [--verbose] — thin CLI wrapping the bot;
   sends Telegram only when new tropical systems are found.

3. scripts/request_tropical_approval.py [--latest --verbose] —
   reads the latest tropical update, registers a twa_ approval,
   sends Telegram + email.

4. scripts/check_tropical_approval.py [--send-notifications --verbose]

5. scripts/publish_approved_tropical_update.py --approval-id <id>

Cron / timer split:
- **systemd timer** with three OnCalendar entries at 08:00 / 14:00 /
  20:00 local: `weather-tropical-watch-monitor.timer` runs a wrapper
  shell script that invokes `tropical_watch.py --send-telegram
  --verbose` then immediately
  `request_tropical_approval.py --latest --verbose`.
- **systemd timer**: `weather-tropical-approval-checker.timer`
  every 15 min.

Hard rules in the LLM approval-message render:
- Reproduce NHC categorical / formation-chance numbers verbatim.
- Never use the words "catastrophic", "unprecedented", "life-
  threatening" unless they appear verbatim in NHC text.
- Always include the system's name (or invest #), advisory number,
  and the NHC product timestamp.
```

---

## Prompt 16.6 — (Optional) HREF × SPC × HRRR Synthesis (private internal briefing)

Skip this if you don't want a model-comparison briefing.

```
Build the HREF × SPC × HRRR Synthesis internal briefing per
SETUP_GUIDE.md §10.11. PRIVATE — never publishes publicly.

Create under weather-agent/:

1. src/weather/href_client.py — NOMADS HREF GRIB idx byte-range
   fetcher. Probabilistic fields (UH 2-5km / UH 0-3km / REFC ≥40)
   and ensemble means (MLCAPE / shear / SRH).

2. src/weather/hrrr_client.py — mirrors href_client shape; pulls
   the matching HRRR deterministic fields for cross-check. Uses
   pygrib (not cfgrib). Documents in a docstring that 0–6 km shear
   is approximated by a 10 m vs 500 mb proxy because NOMADS HRRR
   does not publish a true VWSH:0-6000m AGL field.

3. src/weather/href_severe_extractor.py — build_severe_summary(...)
   returning a 0–4 risk ladder. Tightened thresholds:
   organized-hour gate requires both prob_refc_gt40 ≥ 60% AND
   per-hour MLCAPE ≥ 1000 J/kg; REFC level table capped by peak
   CAPE/shear/SRH; UH75 is primary; REFC may add at most +1 level
   on top, env-permitting. Expose HREF_THRESHOLDS as a single dict
   for retuning.

4. src/weather/hrrr_severe_extractor.py — deterministic 0–4 ladder
   on peak UH 2-5km, REFC, MLCAPE, shear.

5. src/weather/hrrr_href_crosscheck.py — HrrrHrefCrossCheck with
   four verdicts: corroborates / not corroborating (downgrade) /
   hotter than HREF / unavailable.

6. src/weather/href_spc_synthesis.py — ties HREF + SPC + HRRR
   into a synthesis object. HRRR is optional; fetch failures must
   NOT block synthesis.

7. src/weather/href_synthesis_writer.py — prompt + deterministic
   fallback. Both must render an `## At-a-glance` card (5 bullets:
   SPC Day 1 / HREF Day 1 + agreement / HRRR cross-check / peak
   window + storm mode / cycle confidence).

8. scripts/href_vs_spc_synthesis.py [--cycle CC] [--date YYYY-MM-DD]
   [--no-llm] [--force-deliver] [--dry-run]
   [--no-hrrr-crosscheck] [--verbose] [--output-dir DIR] — main
   entrypoint. HTML email body wraps the at-a-glance section in a
   styled card (slate background, blue accent rail, color-coded
   verdict badges — green for corroborates, amber for
   slightly-hot, red for overshoots / not corroborating, gray for
   unavailable). Short Telegram summary mirrors the same shape.

9. tests/ for href_client, hrrr_client, href_severe_extractor,
   hrrr_crosscheck, href_synthesis_writer.

Cron / timer split:
- **systemd timer** with OnCalendar 09:30 / 14:30 / 17:30 local —
  three separate timers (`weather-href-synthesis-morning.timer`,
  `-midday.timer`, `-evening.timer`).
- No approval workflow — private internal briefing.

Hard rules in the LLM prompt:
- HREF level is primary; HRRR cross-check changes the verdict
  wording but not the level.
- Never soften SPC categorical wording.
- HRRR cross-check section must note when the 0–6 km shear proxy
  is in use.
- Tolerate missing HRRR fields by labeling them "unavailable" in
  the cross-check section.
```

---

## Prompt 16.7 — (Optional) Switch MarineCast + public GrowCast to auto-publish + FYI

Only run this after the approval-gated flow has produced clean drafts for months and you genuinely never edit them. See SETUP_GUIDE.md §13.11.

```
Add the "auto-publish + FYI" mode for MarineCast and the PUBLIC daily
GrowCast (the private weekly grower briefing must NOT change).

Create under weather-agent/scripts/:

1. auto_publish_marinecast.py [--dry-run] [--skip-fyi] [--verbose]
   — builds the daily MarineCast, sends Telegram + email FYI
   prefixed with `ℹ️ … FYI — auto-publishing … edit the live
   post directly if you want to tweak it`, synthesizes an
   auto-approved approval record, then calls the same
   publish_approval(...) + record_website_result(...) helpers the
   human-approval path uses (so the existing content-ledger /
   mark_post_attempt dedup guard keeps re-runs safe).

2. auto_publish_growcast.py with the same shape, gated to public
   daily only — must NOT touch the private weekly grower
   briefing.

Cron / timer changes:
- Repoint the MarineCast cron from `marinecast.py --daily
  --request-approval` to `auto_publish_marinecast.py --verbose`.
- Repoint the public GrowCast cron similarly to
  `auto_publish_growcast.py --verbose`.
- Disable the public-GrowCast approval-request cron.
- LEAVE the systemd approval-checker timers enabled — they become
  no-op safety nets.

Do NOT switch Daily Forecast, Severe Weather, Storm Reports, Alert
Explainer, or Tropical Watch to this mode — those stay
approval-gated.

Verify with: `.venv/bin/python scripts/auto_publish_marinecast.py
--dry-run --skip-fyi --verbose` and the GrowCast equivalent. Both
must exit clean with no Facebook / website POSTs.
```

---

## Prompt 16.8 — (Optional) Daily mailbox cleanup

```
Create scripts/cleanup_mailbox.py and install
`weather-mailbox-cleanup.timer` (OnCalendar daily at 18:00 local) to
run `cleanup_mailbox.py --apply --verbose`.

The cleanup should:
- Trash outbound approval-request / result emails older than 3 days.
- Trash approval replies whose approval has reached a terminal
  status (approved / rejected / expired).

Use --dry-run for a no-op trial run. Add a smoke test under tests/.
```

---

## Prompt 17 — Final wiring and verification

```
Now do a full audit of what we built. Show me:

1. The output of: openclaw config get tools.exec
   (must be ask=off, security=full)
2. The full OpenClaw cron list with names, schedules, and timezones.
   Confirm: every approval-checker is a systemd timer, NOT an OpenClaw
   cron. Every OpenClaw cron agentTurn payload has an explicit
   toolsAllow list (the Sounding Email Analyst payload must include
   `image` in toolsAllow).
3. `systemctl --user list-timers 'weather-*'` showing every approval
   checker + email poller + (if built) tropical watch monitor + HREF
   synthesis timers + mailbox cleanup as a systemd timer.
4. The contents of ~/.openclaw/workspace/weather-agent/.env.example
5. A tree of weather-agent/ to depth 2.
6. A summary of every approval-ID prefix in use and which bot owns it
   (dfa_, sva_, mca_, gca_, sra_, aea_, twa_, ewa_, asa_).
7. For each public bot: confirm <bot>_writer.py exists, a smoke test
   exists, and approval_idempotency.py is called from the matching
   request_*_approval.py.
8. If website publishing is wired: confirm publish_to_website_<bot>.py
   exists ONLY for in-scope bots (daily_forecast, marinecast, growcast
   public, severe_weather, alert_explainer, tropical_watch) and NOT
   for the out-of-scope ones.
9. If MarineCast and/or public GrowCast are in auto-publish + FYI
   mode, confirm: the matching OpenClaw cron points at
   auto_publish_<bot>.py, the request-approval cron is disabled, the
   systemd approval-checker timer is still enabled as a safety net,
   and a dry-run of the auto-publish script exits clean.

Then propose three things you would tighten or improve before going
to production. Wait for my go-ahead before changing anything.
```

---

## Prompt 18 — Daily ops tips

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

After all prompts, you should have:

- ✅ ~6–9 OpenClaw cron jobs (LLM-driven generators + private briefings
  only, plus the read-gated sounding analyst), each with an explicit
  `toolsAllow` list on its agentTurn payload
- ✅ ~10–14 systemd user timers (approval checkers, email pollers,
  tropical watch monitor, HREF synthesis morning/midday/evening,
  event-weather intake, mailbox cleanup, sounding poller), enabled
  with linger so they survive logout
- ✅ One approval router hook handling 8–9 ID prefixes (`dfa_`,
  `sva_`, `mca_`, `gca_`, `sra_`, `aea_`, `twa_`, `asa_`, `ewa_` if
  you built the Event Weather Advisor)
- ✅ A `weather-agent/` Python project with one venv, ~40–60 scripts,
  per-bot `<bot>_writer.py` modules with deterministic fallbacks, a
  shared `approval_idempotency.py` guard, an HREF × SPC × HRRR
  synthesis stack if you built it, and a clean tests/ directory
- ✅ Telegram + email + (optional) Facebook + (optional) website all
  wired
- ✅ Trusted public bots (MarineCast + public GrowCast) optionally on
  auto-publish + FYI; everything warning-grade still approval-gated
- ✅ Nothing warning-grade posts publicly without an `APPROVE <id>`
  from your verified Telegram ID

If something's missing or broken, **ask OpenClaw to fix it
conversationally** — that's the whole point of building it this way.

Stay safe. ⛈️
