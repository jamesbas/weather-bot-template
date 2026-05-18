# Build Your Own AI Weather Bot Network with OpenClaw

A step-by-step guide to standing up an OpenClaw environment that monitors official weather data, drafts social-media-ready posts, requests human approval, and publishes only after you say yes — modeled after the **US Weather Warriors (USWW) Delmarva** system, but written so you can adapt it to **any region you cover**.

> **About this guide.** Wherever you see `Delmarva`, `Lewes/Dover/Salisbury`, `DE/MD/VA`, `PHI/AKQ`, or `US Weather Warriors`, swap in your own region, cities, state codes, NWS forecast offices, and brand name. The architecture is identical.

---

## Table of Contents

1. [What you're building](#1-what-youre-building)
2. [Prerequisites](#2-prerequisites)
3. [Install OpenClaw](#3-install-openclaw)
4. [Initial OpenClaw configuration](#4-initial-openclaw-configuration)
5. [Connect Telegram](#5-connect-telegram)
6. [Connect Gmail (SMTP + IMAP)](#6-connect-gmail-smtp--imap)
7. [Connect Facebook Pages (optional)](#7-connect-facebook-pages-optional)
8. [Create the weather-agent project](#8-create-the-weather-agent-project)
9. [The approval workflow pattern](#9-the-approval-workflow-pattern)
10. [Build the agents (cron jobs)](#10-build-the-agents-cron-jobs)
11. [Adapting this to your region](#11-adapting-this-to-your-region)
12. [Operations, maintenance, and security](#12-operations-maintenance-and-security)
13. [Production patterns (lessons from USWW)](#13-production-patterns-lessons-from-usww)

---

## 1. What you're building

A self-hosted assistant that:

- Pulls **official US National Weather Service (NWS), Storm Prediction Center (SPC), and Weather Prediction Center (WPC)** data automatically.
- Drafts public-facing weather posts (daily forecast, marine forecast, severe-weather updates, alert explainers, storm reports, gardening cast).
- Sends drafts to you on **Telegram and email** for approval.
- **Only publishes to Facebook after a valid `APPROVE` reply.**
- Provides private internal briefings (forecaster discussion, chase target advisor) that never auto-publish.
- Runs unattended on a Linux box (Raspberry Pi, mini-PC, VPS — anywhere Node.js + Python run).

The intelligence layer is OpenClaw: it hosts the LLM-driven agent, manages cron jobs, routes Telegram messages, and gates external actions behind your approval.

### Architecture at a glance

```
                  ┌─────────────────────────────────────────────┐
                  │             OpenClaw Gateway                │
 NWS / SPC / WPC ─┤  (cron scheduler, agent runtime, channels)  ├─► Facebook (only after approval)
                  │                                              │
 Telegram ◄──────►│  Hooks: telegram-approval-router             │◄──► Gmail (SMTP send / IMAP poll)
                  │  Cron jobs: ~20 scheduled bots               │
 Email   ◄──────► │  Project: ./weather-agent (Python scripts)   │
                  └─────────────────────────────────────────────┘
```

---

## 2. Prerequisites

| Item | Why |
|---|---|
| Linux host (Pi 5, mini-PC, or small VPS — 4 GB RAM minimum) | Always-on runtime |
| **Node.js 20+ and npm** | OpenClaw runtime |
| **Python 3.11+** with `venv` | Weather scripts |
| A **GitHub Copilot subscription**, **Anthropic API key**, **OpenAI API key**, or local LM Studio | LLM model provider |
| **Telegram account + a phone** | Approvals + notifications |
| **Gmail account** (use a dedicated one, not your personal inbox) | Email approval channel |
| **Facebook Page** + admin access | Public publishing target (optional) |
| Domain knowledge of your local NWS forecast offices | To configure the right data sources |

Find your NWS offices at [weather.gov](https://www.weather.gov/) — click your area on the map; the 3-letter office code (e.g. `PHI`, `OKX`, `LWX`) is in the URL.

---

## 3. Install OpenClaw

OpenClaw installs from npm and runs as a local gateway service.

```bash
# Install Node 20+ first (use nvm or your distro package manager)
node -v   # should be >= 20

# Install OpenClaw globally
npm install -g openclaw

# First-time setup wizard
openclaw config
```

The wizard will ask you:

- **Workspace path** — accept the default `~/.openclaw/workspace`
- **Gateway mode** — `local`
- **Bind** — `loopback` (recommended on a single host)
- **Model provider** — pick one (GitHub Copilot is the easiest if you already have it; OpenAI/Anthropic also work)

When the wizard finishes:

```bash
openclaw gateway start         # start the background service
openclaw gateway status        # confirm "Runtime: running"
openclaw doctor                # health check
```

You should now be able to talk to the bot from the OpenClaw TUI:

```bash
openclaw                       # opens the terminal UI
```

### Disable per-command approval prompts (for trusted single-user setups)

OpenClaw defaults to asking before every shell command. For an unattended weather bot — where **the only thing you care about approving is the Facebook post** — turn this off:

```bash
openclaw config set tools.exec.ask off
openclaw config set tools.exec.security full
openclaw gateway restart
```

> ⚠️ Only do this on a host where you are the sole operator. The Facebook approval flow you'll build below is what protects publishing.

---

## 4. Initial OpenClaw configuration

Edit `~/.openclaw/openclaw.json` (or use `openclaw config set <path> <value>`) to lock down the basics:

```json
{
  "agents": {
    "defaults": {
      "workspace": "/home/<you>/.openclaw/workspace",
      "model": { "primary": "github-copilot/gpt-5.4-mini" }
    }
  },
  "session": { "dmScope": "per-channel-peer" },
  "commands": { "ownerAllowFrom": ["telegram:<your-telegram-user-id>"] },
  "bindings": [
    { "type": "route", "agentId": "main", "match": { "channel": "telegram" } }
  ]
}
```

`commands.ownerAllowFrom` is critical: it restricts owner-level commands to *your* Telegram user ID so a stranger who finds your bot can't drive it.

---

## 5. Connect Telegram

### 5.1 Create a Telegram bot

1. Open Telegram → search for **@BotFather**.
2. Send `/newbot`, answer the prompts, and save the **bot token** it returns.
3. Send `/setprivacy` → choose your bot → **Disable** (so it can read group messages if you ever use one).

### 5.2 Get your numeric Telegram user ID

Send any message to **@userinfobot** in Telegram — it will reply with your numeric ID. Save it.

### 5.3 Wire the token into OpenClaw

```bash
mkdir -p ~/.openclaw/credentials
echo "<your-bot-token>" > ~/.openclaw/credentials/telegram-bot-token.txt
chmod 600 ~/.openclaw/credentials/telegram-bot-token.txt
```

Then in `~/.openclaw/openclaw.json`:

```json
"channels": {
  "telegram": {
    "enabled": true,
    "tokenFile": "/home/<you>/.openclaw/credentials/telegram-bot-token.txt",
    "groups": { "*": { "requireMention": true } }
  }
}
```

Restart and test:

```bash
openclaw gateway restart
# Now message your bot in Telegram. It should respond.
```

---

## 6. Connect Gmail (SMTP + IMAP)

You'll use Gmail two ways:

- **SMTP** — to send approval-request emails to yourself / your team.
- **IMAP** — to receive `APPROVE <id>` replies (and, optionally, sounding analysis requests).

### 6.1 Create an App Password

1. Use a **dedicated Gmail account** (e.g. `yourbrandweatherbot@gmail.com`).
2. Enable **2-Step Verification** on that account.
3. Visit [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
4. Create an app password named "WeatherBot" and **save the 16-character password**.

### 6.2 Store credentials in `.env`

You'll create the project in §8; for now just remember the variables you'll set:

```bash
GMAIL_SMTP_USER=yourbrandweatherbot@gmail.com
GMAIL_APP_PASSWORD=<the 16-char app password>
GMAIL_APPROVAL_RECIPIENTS=you@example.com,coforecaster@example.com
```

> Never commit `.env` to GitHub. Add `.env` to `.gitignore`.

---

## 7. Connect Facebook Pages (optional)

Skip if you only want Telegram/email outputs.

1. Go to [developers.facebook.com](https://developers.facebook.com) → **Create App** → type **Business**.
2. Add the **Pages** product.
3. In the **Graph API Explorer**, generate a **Page Access Token** with these permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `pages_show_list`
4. Convert the short-lived token to a **long-lived (60-day) token** using:
   ```
   GET https://graph.facebook.com/v24.0/oauth/access_token?
     grant_type=fb_exchange_token&
     client_id=<APP_ID>&
     client_secret=<APP_SECRET>&
     fb_exchange_token=<SHORT_LIVED_TOKEN>
   ```
5. Get your **Page ID** from your Facebook Page → About → "Page ID".

Save these in `.env`:

```bash
FACEBOOK_PAGE_ID=<your page id>
FACEBOOK_PAGE_ACCESS_TOKEN=<long-lived token>
FACEBOOK_GRAPH_API_VERSION=v24.0
```

> Long-lived Page tokens still expire. Add a calendar reminder to refresh every ~50 days, or build a refresh-token cron job.

---

## 8. Create the weather-agent project

This is the Python project that holds your scripts. The OpenClaw cron jobs will simply invoke these scripts.

```bash
cd ~/.openclaw/workspace
mkdir weather-agent && cd weather-agent
python3 -m venv .venv
source .venv/bin/activate
pip install requests python-dateutil python-dotenv beautifulsoup4 pillow imapclient
mkdir -p scripts src/weather state output logs
touch .env .env.example
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
echo "output/" >> .gitignore
echo "state/" >> .gitignore
```

### 8.1 `.env` template

Drop this in `.env.example` (publishable) and fill `.env` with real values (never commit):

```bash
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=                # your numeric user ID
TELEGRAM_APPROVER_IDS=           # comma-separated approver user IDs

# Email
GMAIL_SMTP_USER=
GMAIL_APP_PASSWORD=
GMAIL_APPROVAL_RECIPIENTS=

# Facebook
FACEBOOK_PAGE_ID=
FACEBOOK_PAGE_ACCESS_TOKEN=
FACEBOOK_GRAPH_API_VERSION=v24.0

# Region — change these for your area
WX_REGION_NAME=Delmarva
WX_NWS_OFFICES=PHI,AKQ           # comma-separated 3-letter office codes
WX_STATE_CODES=DE,MD,VA          # alert filtering
WX_FORECAST_POINTS=Lewes:38.7783,-75.1394;Dover:39.1582,-75.5244;Salisbury:38.3607,-75.5994
WX_TIMEZONE=America/New_York

# Per-bot tunables
MARINECAST_APPROVAL_EXPIRES_HOURS=6
ALERT_EXPLAINER_DEDUP_TTL_HOURS=12

# --- Optional: second publish target (your own website) ---
# If set, approved content posts to your website in parallel with
# Facebook via an HMAC-signed POST. See §13.4. Leave blank to skip.
USWW_WEBSITE_BASE_URL=
USWW_WEBSITE_API_KEY=
USWW_WEBSITE_HMAC_SECRET=
USWW_WEBSITE_DISABLED=             # set to 1 to kill-switch without code change

# --- Optional: Event Weather Advisor (per-customer paid workflow) ---
# Only needed if you build the Event Weather Advisor bot.
EVENT_WEATHER_INTERNAL_RECIPIENTS=
EVENT_WEATHER_DEFAULT_TIMEZONE=America/New_York
```

### 8.2 Source-data foundations

You need helpers to pull NWS data. The official endpoints (free, no key required):

| Source | URL pattern | Use for |
|---|---|---|
| Forecast | `https://api.weather.gov/points/{lat},{lon}` then `/forecast` | Daily forecasts |
| Active alerts | `https://api.weather.gov/alerts/active?area={STATE}` | Tornado, severe T'storm, flood, marine |
| AFD (forecast discussion) | `https://api.weather.gov/products/types/AFD/locations/{office}` | Forecaster reasoning |
| SPC convective outlooks | `https://www.spc.noaa.gov/products/outlook/day1otlk_cat.nolyr.geojson` (and day2/day3) | Severe risk |
| SPC mesoscale discussions | `https://www.spc.noaa.gov/products/md/` (HTML) | Active threat windows |
| WPC excessive rainfall | `https://www.wpc.ncep.noaa.gov/qpf/excessive_rainfall_outlook_ero.php` | Flash flood risk |
| NWS marine zones | `https://api.weather.gov/zones/marine` | MarineCast |
| Local Storm Reports | `https://www.spc.noaa.gov/climo/reports/today.html` (and `_filtered.csv`) | Storm Reports Bot |

Always include a `User-Agent` header (NWS requires it):

```python
HEADERS = {"User-Agent": "YourBrandWeatherBot (contact@example.com)"}
```

### 8.3 Suggested project layout

```
weather-agent/
├── .env                       # secrets (gitignored)
├── .env.example
├── README.md
├── requirements.txt
├── src/weather/
│   ├── nws_client.py          # forecast + alerts
│   ├── spc_client.py          # convective outlooks + MDs
│   ├── wpc_client.py          # rainfall outlooks
│   ├── afd_client.py          # forecast discussions
│   ├── approval_store.py      # JSON-backed pending approvals
│   ├── facebook_publisher.py  # Graph API POST
│   ├── telegram_client.py     # bot send / IMAP-style polling
│   ├── email_client.py        # SMTP send + IMAP poll
│   └── geo.py                 # county/zone polygon checks
├── scripts/
│   ├── daily_forecast.py
│   ├── request_daily_forecast_approval.py
│   ├── check_daily_forecast_approval.py
│   ├── publish_approved_daily_forecast.py
│   ├── ... (one of each per bot)
└── state/                      # approval JSON, dedup state
```

---

## 9. The approval workflow pattern

Every public-facing bot uses the **same four-step pattern**. Internalize it and you can build any of them.

```
 ┌────────────────┐  ┌─────────────────────────┐  ┌─────────────────┐  ┌────────────────────┐
 │ 1. Generator   │─►│ 2. Approval Requester   │─►│ 3. Approval     │─►│ 4. Publisher       │
 │  (cron 1)      │  │    Telegram + email     │  │    Checker      │  │    (only on APPROVE)│
 │  draft .md     │  │    write pending state  │  │    (cron 2,     │  │    Facebook post   │
 └────────────────┘  └─────────────────────────┘  │     every 15m)  │  └────────────────────┘
                                                  └─────────────────┘
```

### 9.1 Approval IDs

Each draft gets a short opaque ID like `dfa_a1b2c3d4` (`dfa_` = "daily forecast approval"). The ID is included in the Telegram and email message:

```
US Weather Warriors — Daily Forecast Approval
ID: dfa_a1b2c3d4

[draft body…]

To publish, reply to this Telegram message with:
APPROVE dfa_a1b2c3d4

To reject:
REJECT dfa_a1b2c3d4
```

### 9.2 Approval store

A simple JSON file in `state/`:

```json
{
  "dfa_a1b2c3d4": {
    "kind": "daily_forecast",
    "draft_path": "output/2026-05-15/final_post.md",
    "created_ts": 1715812800,
    "expires_ts": 1715834400,
    "status": "pending",
    "approved_by": null
  }
}
```

### 9.3 Telegram approval router (OpenClaw hook)

This is the magic that turns `APPROVE dfa_xxxx` Telegram messages into approval state changes. Create the hook in your workspace:

```
~/.openclaw/workspace/hooks/weather-approval-router/
├── HOOK.md
└── handler.js
```

**`HOOK.md`:**
```yaml
---
name: weather-approval-router
description: "Route exact Telegram APPROVE/REJECT messages into the weather approval workflow"
metadata:
  {
    "openclaw":
      {
        "emoji": "☀️",
        "events": ["message:received", "message:preprocessed"],
        "requires": { "bins": ["python3"] }
      }
  }
---
```

**`handler.js`** (skeleton — adapt the regex and script path):
```js
import { execFile } from 'node:child_process';

const PROJECT = '/home/<you>/.openclaw/workspace/weather-agent';
const PYTHON  = `${PROJECT}/.venv/bin/python`;
const SCRIPT  = `${PROJECT}/scripts/handle_routed_telegram_approval.py`;
const RE = /^(APPROVE|REJECT)\s+(dfa_|sva_|mca_|gca_|sra_|aea_)[A-Za-z0-9_-]+\s*$/i;

export default async function (event) {
  if (event.type !== 'message' || !['received','preprocessed'].includes(event.action)) return;
  const meta = event.context?.metadata || {};
  if ((meta.channel || event.context?.channelId) !== 'telegram') return;
  const text = (event.context?.content || '').trim();
  if (!RE.test(text)) return;

  await new Promise(r => execFile(PYTHON, [SCRIPT, '--text', text,
      '--sender-id', String(meta.senderId || '')],
      { cwd: PROJECT, timeout: 60000 }, () => r()));
}
```

That hook makes Telegram replies actionable. The Python handler script verifies the sender ID is in `TELEGRAM_APPROVER_IDS`, marks the approval as approved, and triggers the publisher.

---

## 10. Build the agents (cron jobs)

Below is the full bot lineup. Each one is a cron job in OpenClaw. You can create them from the TUI, the CLI, or directly via the `cron` tool from inside an agent session.

### Cron job creation reference

From an agent session, ask:

> Create a cron job that runs `cd ~/.openclaw/workspace/weather-agent && source .venv/bin/activate && python scripts/daily_forecast.py --phase morning` every day at 6:30 AM ET, isolated session, 1200s timeout.

Or via the TUI: **Cron → Add → fill in name, schedule (cron expr), session target = isolated, payload = agentTurn with the message above**.

> All schedules below use **cron expressions in your local timezone** (set `tz` on each job).

---

### 10.1 Daily Forecast Bot 🌤

**Purpose:** Generate a public morning + afternoon forecast post for your region.

| Job | Schedule | Script |
|---|---|---|
| Morning generator | `30 6 * * *` | `python scripts/daily_forecast.py --phase morning` |
| Morning approval request | `40 6 * * *` | `python scripts/request_daily_forecast_approval.py --latest` |
| Afternoon generator | `0 15 * * *` | `python scripts/daily_forecast.py --phase afternoon` |
| Afternoon approval request | `10 15 * * *` | `python scripts/request_daily_forecast_approval.py --latest` |
| Approval checker | every 15 min | `python scripts/check_daily_forecast_approval.py --send-notifications` |

**What the generator does:**
1. Pulls forecasts for each `WX_FORECAST_POINTS` city.
2. Pulls active alerts for each `WX_STATE_CODES`.
3. Pulls AFDs from each `WX_NWS_OFFICES`.
4. Asks the LLM (via OpenClaw) to write a friendly Facebook post.
5. Saves to `output/YYYY-MM-DD/final_post.md`.

---

### 10.2 Severe Weather Bot ⛈

**Purpose:** Watch SPC outlooks and mesoscale discussions, issue an update only when something *meaningful* changes.

| Job | Schedule | Script |
|---|---|---|
| SPC/MD checker | `0 10,13,16,19 * * *` | `python scripts/check_spc_delmarva.py` (rename to your region) |
| Approval checker | every 15 min | `python scripts/check_severe_weather_approval.py --send-notifications` |

The checker compares against the last seen state. **Only** if the categorical risk for your region changed (e.g. Marginal → Slight) or a new MD intersects your polygon does it call `request_severe_weather_approval.py`. This keeps signal-to-noise high.

---

### 10.3 Alert Explainer Bot 📣

**Purpose:** Translate raw NWS warnings ("Tornado Warning … 50 dBZ … TVS …") into plain English, post-with-map.

| Job | Schedule | Script |
|---|---|---|
| Runner | every 15 min | `python scripts/run_alert_explainer.py` |
| Approval checker | every 15 min | `python scripts/check_alert_explainer_approval.py --send-notifications` |

Dedup logic in `state/alert_explainer_seen_items.json` ensures each warning is processed once. The runner generates a draft + a county map PNG.

---

### 10.4 Storm Reports Bot 📍

**Purpose:** After a severe-weather day, summarize confirmed Local Storm Reports (LSR) inside your region.

| Job | Schedule | Script |
|---|---|---|
| Generator (post-event, manual or evening cron) | `0 22 * * *` | `python scripts/storm_reports_monitor.py` |
| Approval checker | every 15 min | `python scripts/check_storm_reports_approval.py --send-notifications` |

Filters LSRs by county FIPS or polygon, groups by event type (tornado, hail, wind, flooding), and drafts a recap.

---

### 10.5 MarineCast Bot 🌊

**Purpose:** Daily marine forecast for boaters and coastal residents.

| Job | Schedule | Script |
|---|---|---|
| Daily draft + approval request | `0 5 * * *` | `python scripts/marinecast.py --daily --request-approval` |
| Approval checker | every 15 min | `python scripts/check_marinecast_approval.py --send-notifications` |

Skip this bot entirely if you cover an inland region.

---

### 10.6 GrowCast Bot 🌱

**Purpose:** Seasonal (April–October) gardening / lawn / small-farm guidance based on weather.

| Job | Schedule | Script |
|---|---|---|
| Daily public draft | `0 7 * 4-10 *` | `python scripts/growcast.py --daily --public` |
| Daily approval request | `15 7 * * *` | `python scripts/request_growcast_approval.py --latest` |
| Weekly private briefing | `0 8 * * 0` | `python scripts/growcast.py --weekly --private --send-email` |
| Approval checker | every 15 min | `python scripts/check_growcast_approval.py --send-notifications` |

The `* 4-10 *` portion of the cron expression limits this to April through October.

---

### 10.7 Forecaster Briefing 🧠 (private)

**Purpose:** Internal-only technical briefing — instability, shear, lapse rates, storm mode, limiting factors. Emailed to you and your team. **Never** posts publicly.

| Job | Schedule | Script |
|---|---|---|
| Daily briefing | `45 6 * * *` | `python scripts/forecaster_briefing.py --send-all` |

No approval workflow because nothing public happens.

---

### 10.8 Chase Target Advisor 🚗 (private)

**Purpose:** Private storm-chase recommendation. Suggests primary + secondary targets, timing window, safety notes, and **only fires when severe potential is at least Marginal**.

| Job | Schedule | Script |
|---|---|---|
| Morning | `0 7 * * *` | `python scripts/chase_target_advisor.py --send-all` |
| Hourly afternoon | `0 10-21 * * *` | same |

The cron prompt should explicitly say: *"Only send anything if `chase_target_recommended: True` and `severe_potential_level >= Marginal` and safety checks do not veto."*

---

### 10.9 Sounding Email Analyst 📈 (private utility)

**Purpose:** Authorized teammates email a Skew-T / hodograph image to the bot's Gmail; the bot replies with a structured severe-weather analysis of the sounding.

| Job | Schedule | Script |
|---|---|---|
| IMAP watcher | every 10 min | `python scripts/poll_sounding_email_requests.py` |

The cron *prompt* (not the script) instructs the agent: read each new image with the `image` tool, perform the model-sounding analysis, then run `scripts/send_sounding_email_response.py` to reply by email. Restrict allowed senders inside the script — never trust the LLM to enforce that.

---

### 10.10 Recap of recommended schedule cadence

- **Generators / drafters** — once or twice daily at the right time.
- **Approval checkers** — every **15 minutes**. Never set a checker to every 5 minutes; you'll burn LLM tokens for almost no benefit.
- **Watchers (alerts, soundings)** — every 10–15 minutes is plenty.
- **Heavy or expensive jobs** — schedule with `tz` set to your local timezone, not UTC.

---

## 11. Adapting this to your region

The repo is generic if you do all of these substitutions:

| Generic field | Where to set | Example value |
|---|---|---|
| Region name | `WX_REGION_NAME` in `.env`, prompts, brand strings | `Tampa Bay`, `Front Range`, `Pacific NW` |
| Forecast cities | `WX_FORECAST_POINTS` | `Tampa:27.95,-82.46;St Pete:27.77,-82.64` |
| State codes for alerts | `WX_STATE_CODES` | `FL` |
| NWS office codes for AFDs | `WX_NWS_OFFICES` | `TBW,MLB` (Tampa Bay + Melbourne) |
| Marine zones (if used) | hard-code in `marinecast.py` | `AMZ550,AMZ555,…` |
| County polygon for SPC/storm-reports filtering | `src/weather/geo.py` | GeoJSON of your counties |
| Timezone | every cron job's `tz` | `America/Chicago`, `America/Denver`, etc. |
| Brand emoji + signature | SOUL.md and prompt templates | up to you |

Find your NWS marine zone codes at [weather.gov/marine](https://www.weather.gov/marine). Find your office code at [weather.gov](https://www.weather.gov/) — click your area on the map.

### Outside the United States?

The NWS API only covers the US. If you're elsewhere:

- **EU**: replace with [Open-Meteo](https://open-meteo.com/) (free) or your national met service's API.
- **UK**: Met Office DataPoint.
- **Canada**: Environment Canada GeoMet.
- **AU**: BOM via FTP or third-party scrapers.

The OpenClaw + cron + approval scaffolding doesn't change — only the data clients in `src/weather/` do.

---

## 12. Operations, maintenance, and security

### Running it 24/7

Easiest path: a Raspberry Pi 5 (8 GB) with the OpenClaw systemd service. The installer registers `openclaw-gateway.service`. Confirm with:

```bash
systemctl --user status openclaw-gateway.service
journalctl --user -u openclaw-gateway.service -n 100 --no-pager
```

### Logs to watch

- `/tmp/openclaw/openclaw-YYYY-MM-DD.log` — gateway runtime
- `~/.openclaw/logs/weather-approval-router.log` — Telegram routing diagnostics
- `~/.openclaw/workspace/weather-agent/logs/` — script-level logs

### Token rotation

| Token | Lifetime | Rotation |
|---|---|---|
| Telegram bot token | indefinite | only if compromised; revoke via @BotFather |
| Gmail app password | indefinite | rotate annually; revoke via Google account |
| Facebook Page access token | ~60 days | refresh proactively (cron job recommended) |

### Common pitfalls

- **Forgetting `User-Agent` on NWS calls** → 403s. Always set it.
- **Posting without a "have multiple ways to receive warnings" disclaimer** on warning bots → use a standard closer in every Alert Explainer post.
- **Letting the bot speak in absolutes** → always include your hedging language ("could", "may", "expected") in prompt templates.
- **Hardcoding lat/lon in code instead of `.env`** → makes regional adaptation painful for forks.
- **Sending approval requests to a Telegram group instead of DM** → strangers can `APPROVE`. Restrict to your numeric user ID via `TELEGRAM_APPROVER_IDS` and verify in the handler.

### What you should and should not approve

- ✅ **Public Facebook posts** — always require human approval.
- ✅ **Email blasts** to subscribers — always require approval.
- ❌ **Internal Telegram messages to yourself** — no approval needed.
- ❌ **Private email briefings to your forecast team** — no approval needed.
- ❌ **Cached data writes / NWS pulls** — no approval needed.

The whole point of this architecture is: *the only friction is at the moment of public publication.* Don't add friction anywhere else.

---

## Closing notes

You now have a blueprint for an LLM-driven weather operation that:

- Ingests official NWS/SPC/WPC data unattended.
- Drafts, hedges, and posts in your brand voice.
- Asks you nicely before saying anything in public.
- Costs roughly the price of a small VPS plus your model provider's bill.

If you build something with this, please credit **US Weather Warriors** and link back to the [USWW repo](https://github.com/) — and let us know what region you're covering. Forks, improvements, and pull requests welcome.

Stay safe out there. ⛈️

— *JaimeClaw, US Weather Warriors*

---

## 13. Production patterns (lessons from USWW)

The sections above get you to a working bot. These are the patterns
we added in production after running USWW Delmarva for real — each
one solves a specific failure mode we hit.

### 13.1 Use systemd user timers for plain pollers (not OpenClaw cron)

**The problem we hit (2026-05-15):** every OpenClaw cron `agentTurn`
run hard-codes `tools.exec.security` to `allowlist` mode — even when
your global config says `full`. That means every `python scripts/X.py`
call inside an agentTurn cron generates an `/approve` request, which
lands in Telegram. The 7 USWW approval-checker crons were generating
~700 Telegram approval requests a day.

**The fix:** approval checkers and email pollers are pure Python with
no LLM in the loop. They don't need a cron `agentTurn` at all. Run
them as **systemd user timers** instead. The python scripts execute
directly, no agent runtime, no allowlist override, no Telegram spam.

**When to use which:**

| Job type | Scheduler | Why |
|---|---|---|
| Drafting a forecast post (LLM writes copy) | OpenClaw cron `agentTurn` | needs the agent loop |
| Private forecaster briefing (LLM reasoning) | OpenClaw cron `agentTurn` | needs the agent loop |
| Multi-step LLM decisions (chase target, severe-check + draft) | OpenClaw cron `agentTurn` | needs the agent loop |
| Approval-reply checker (poll JSON + Gmail IMAP + maybe publish) | **systemd user timer** | pure Python, no LLM |
| Email IMAP poller (sounding requests, etc.) | **systemd user timer** | pure Python, no LLM |
| Mailbox cleanup (trash old approval emails) | **systemd user timer** | pure Python, no LLM |
| Active-alert poller that drafts on hit | OpenClaw cron `agentTurn` | LLM-driven draft on match |

**Unit-file template** — drop these under
`~/.config/systemd/user/` and `daemon-reload && enable --now`:

`weather-<bot>-approval-checker.service`:
```ini
[Unit]
Description=Weather Bot — <bot> approval checker

[Service]
Type=oneshot
ExecStart=/home/<you>/.openclaw/workspace/weather-agent/systemd/run-checker.sh check_<bot>_approval.py --send-notifications --verbose
TimeoutStartSec=900
Nice=10

[Install]
WantedBy=default.target
```

`weather-<bot>-approval-checker.timer`:
```ini
[Unit]
Description=Run weather <bot> approval checker every 15 min

[Timer]
OnBootSec=5min
OnUnitInactiveSec=15min
AccuracySec=30s
Persistent=true
Unit=weather-<bot>-approval-checker.service

[Install]
WantedBy=timers.target
```

`systemd/run-checker.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/<you>/.openclaw/workspace/weather-agent
source .venv/bin/activate
exec python "scripts/$@" 2>&1 | tee -a "logs/${1%.py}.log"
```

**Enable linger** so timers run when you're logged out:
```bash
sudo loginctl enable-linger <you>
systemctl --user daemon-reload
systemctl --user enable --now weather-daily-forecast-approval-checker.timer
systemctl --user list-timers 'weather-*'
```

### 13.2 `toolsAllow` on OpenClaw cron `agentTurn` payloads

For the LLM-driven cron jobs that *do* belong in OpenClaw cron
(generators, briefings, severe-weather checks), explicitly set
`toolsAllow` on the payload to avoid the same approval-timeout stall
at a smaller scale:

```js
{
  payload: {
    kind: "agentTurn",
    message: "Run the daily forecast generator + approval request …",
    toolsAllow: ["exec", "read"]
    // add "write", "image" only if the specific job needs them
  }
}
```

Without this, the cron sub-agent inherits the allowlist default and
stalls waiting for `/approve` on the first `python` call.

### 13.3 LLM writer + deterministic safety-net fallback

The naive way to write a forecast is "feed sources to LLM, take
output, post." That breaks the moment the model returns garbage,
times out, or the gateway has a hiccup. Production pattern:

1. Keep your existing **deterministic generator** (Python rendering of
   a Jinja-style template from the source data). This is the
   *fallback*.
2. Add a `src/weather/<bot>_writer.py` module:
   - `build_prompt(source_bundle) -> str` — renders a structured
     prompt anchored on the deterministic data.
   - `write_post(source_bundle, fallback_callable) -> (text, llm_used, fallback_reason)`
     — calls `openclaw capability model run --prompt <file> --gateway --json`
     and returns the LLM text, falling back to the deterministic
     output on subprocess error, timeout, non-OK envelope, or empty
     `outputs[0].text`.
3. Save per-run artifacts next to the normal output:
   - `<bot>_llm_prompt.txt`
   - `<bot>_llm_meta.json` — `{llm_used, fallback_reason, model, generated_at}`
4. Add a `--no-llm` CLI flag on every bot to force deterministic mode
   for diffing and testing.
5. Add a smoke-test per bot covering: prompt-contents check, success
   path, subprocess-error fallback, non-OK-envelope fallback.

**Prompt design conventions** (apply to every public bot):

- Numbered hard rules forbidding fabrication of CAPE / shear / lapse
  rates / rainfall / dewpoints / frost dates / soil temps / hazard
  categories.
- No softening of NWS or SPC hazard wording.
- SPC categorical wording (Marginal / Slight / Enhanced / Moderate /
  High / PDS) reproduced **verbatim** from source data.
- Per-bot allowed-emoji list (usually one header emoji only) and a
  per-bot hashtag whitelist.
- Target word count.
- Standard public closer: "<brand> is sharing official weather
  information for awareness. Follow NWS warnings and local emergency
  guidance."
- Public bots: brand sign-off above hashtags.
- Private bots (forecaster briefing): no emojis, no hashtags, no
  sign-off; technical shorthand allowed; explicit rule to say
  "unavailable from current source data" rather than invent values.

The writers should **not pin a model** by default — omit `--model` and
let the gateway default pick. A specific model can be set per-bot via
the writer dataclass `model` field if you need to pin one (e.g. send
the forecaster briefing to a larger model than the daily post).

### 13.4 Approval-request idempotency guard

**The problem we hit (2026-05-17):** a cron sub-agent
second-guessed a path and ran `python scripts/marinecast.py
--request-approval` **three times** in one cron fire. Result: 3
approval IDs + 3 Telegram + 3 emails for the same forecast date.

**The fix:** every `--request-approval` code path checks for an
existing non-dry-run, non-expired pending approval for the same
`forecast_date` **before** calling `create_approval(...)`. If one
exists, print `REUSED_EXISTING_APPROVAL_ID=<id>` and exit 0 without
creating a duplicate or re-sending notifications.

Minimal helper module — `src/weather/approval_idempotency.py`:
```python
from datetime import datetime, timezone

def find_existing_pending_approval(store, forecast_date, dry_run=False):
    """Return the most recent pending, non-expired, non-dry-run approval
    for forecast_date, or None."""
    now = datetime.now(timezone.utc).timestamp()
    candidates = [
        a for a in store.pending()
        if a.get("forecast_date") == forecast_date
        and a.get("status") == "pending"
        and not a.get("dry_run", False)
        and float(a.get("expires_ts", 0)) > now
    ]
    candidates.sort(key=lambda a: a.get("created_ts", 0), reverse=True)
    return candidates[0] if candidates else None
```

Wire it into every `request_*_approval.py` and into `marinecast.py
--request-approval` and the equivalent inline-request paths.

### 13.5 Same-day publish-path dedup gotcha

If a deterministic run posts using `final_post.md` and then you
re-run the LLM writer the same day, the publisher's `mark_post_attempt`
dedup guard will block the second post because the path matches.

**Workaround:** always save LLM-writer output to a sibling file with
an `_llm.md` suffix so a same-day re-post never collides. Update the
approval's stored file reference to point at the `_llm.md` file before
calling the publisher.

Better: from day one, write LLM output to `<basename>_llm.md` and
deterministic fallback output to `<basename>.md` so the paths are
always distinct.

### 13.6 Second publish target: your own website (parallel to Facebook)

USWW added a second publish target on 2026-05-16: an HMAC-signed POST
to the USWW website that mirrors approved Facebook content. The
pattern is general enough to drop into this template.

**Design rules:**

- Website publish runs **after** the Facebook publish, inside a
  try/except that must **not** block Facebook on failure. Facebook is
  the authoritative "post happened" signal.
- HMAC-SHA256 over `timestamp + "." + rawBody`, sent as
  `X-USWW-Api-Key`, `X-USWW-Timestamp`,
  `X-USWW-Signature: sha256=<hex>` headers.
- Local idempotency: skip if the approval record's
  `website_status == "posted"`. Server idempotency: dedupe on
  `approvalId` as a backstop.
- Kill switch via `WEBSITE_DISABLED=1` env var (don't require a code
  change to pause the integration).

**Files to add:**

- `src/weather/website_client.py` exposing `WebsiteClient`,
  `excerpt_from_markdown`, `record_website_result`,
  `already_posted_to_website`.
- `scripts/publish_to_website_<bot>.py` per in-scope bot.
- Wire each `scripts/publish_to_website_<bot>.py` into the matching
  approval checker right after the Facebook publish call.

**Approval-record fields after a website attempt:**
`website_status` (`posted`/`post_failed`/`disabled`), `website_post_id`,
`website_public_url`, `website_published_at`, `website_error`,
`website_status_code`.

**Scope discipline:** public bots only. Private bots (forecaster
briefing, chase target advisor, sounding analyst, GrowCast private
weekly briefing, Event Weather Advisor) must NOT post to the website.

### 13.7 Per-customer paid workflow: Event Weather Advisor

A different shape of bot worth knowing about: per-event weather
advisories for paying customers (outdoor weddings, concerts,
festivals, sports). Not on a cron — operator-driven, scaffolded via:

1. `event_weather_intake.py` — register a customer event
   (datetime, lat/lon, venue, customer contact).
2. `event_weather_prepare_update.py` — deterministic Python: pulls
   NWS active alerts + forecast for the event point, AFD context, SPC
   categorical (when ≤ 3 days out), WPC excessive rainfall,
   climatology (NOAA normals + 30-yr historical analog + CPC
   outlooks) for far-out events. Computes a deterministic risk
   summary (Overall + Rain / Thunderstorm / Severe / Wind / Heat /
   Cold / Flooding / Setup-Teardown). Outputs a structured LLM
   prompt packet.
3. LLM stage — the operator (or a script) hands the prompt packet to
   the OpenClaw gateway default LLM, which produces a dual-output
   document with `<<<CUSTOMER_UPDATE_BELOW>>>` as a literal marker
   between the internal review and the customer-facing email.
4. `event_weather_send_email.py --send-internal` / `--send-customer`
   — explicit operator-gated send. Never automatic.
5. `event_weather_due_updates.py` — candidate runner if/when you
   want a recurring "is anything due for a refresh?" check.

**Hard rules** (encode in the LLM prompt):

- Never recommend cancellation / postponement unless overall risk is
  `High` **or** an active severe/flood warning is in the source
  bundle.
- Never fabricate forecast values — say "unavailable from current
  source data."
- Never present climatology as a forecast. Use "historically," "on
  average," "the CPC outlook leans toward."
- `data_strategy == climate_only` (event beyond NWS forecast window)
  must state that plainly; confidence stays Low.
- Customer email always closes with a line directing the customer to
  monitor official NWS warnings independently + your brand sign-off.
- **Never** publishes to Facebook or the website.

### 13.8 Mailbox cleanup

USWW outbound approval-request / result emails accumulate in Sent and
replies pile up in Inbox. A small `scripts/cleanup_mailbox.py`
(systemd timer, daily at 18:00 local) trashes outbound USWW approval/
result emails > 3 days old and approval replies whose approval has
reached a terminal status. Nothing fancy — just keeps the mailbox
manageable.

### 13.9 Heartbeat sanity

If you wire heartbeat checks for the main session, batch them in a
shared `HEARTBEAT.md` checklist (calendar + email + alerts in one
turn) rather than spawning one cron per check. Reserve cron for jobs
that need exact timing or isolated context.

### 13.10 Sounding analyst: read-gated pattern

The Sounding Email Analyst is the one cron that legitimately needs
both an IMAP poll *and* an LLM image-analysis step. Split it in two:

- A **systemd timer** runs `poll_sounding_email_requests.py` every 10
  min and writes a small `state/sounding_pending.json` (count of
  unprocessed requests + their paths).
- An **OpenClaw cron** `agentTurn` runs every 15 min and immediately
  reads `state/sounding_pending.json`. If `count == 0`, the agent
  replies `STILL_NOTHING_TO_DO` and exits early without burning
  tokens. Otherwise it processes the pending images with the `image`
  tool and replies via `scripts/send_sounding_email_response.py`.

This read-gated pattern keeps LLM token burn near zero on quiet days
while retaining LLM analysis on busy days.

---
