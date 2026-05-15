# Quickstart — Get One Weather Bot Running in 30 Minutes

Goal: from a clean Linux box to **your first AI-drafted weather post sitting in your Telegram inbox awaiting approval**, in under half an hour.

Once that works, you can come back and add the rest of the bots using [`RUNBOOK_PROMPTS.md`](./RUNBOOK_PROMPTS.md).

> 📖 If you hit anything confusing, the long-form details are in [`SETUP_GUIDE.md`](./SETUP_GUIDE.md).

---

## What you'll have at the end

✅ OpenClaw running on your host
✅ A Telegram bot you can chat with
✅ Gmail wired for sending email
✅ One working bot (**Daily Forecast**) drafting a post for your region
✅ The post arrives in Telegram waiting for your `APPROVE <id>` reply

Skip Facebook for now — get the loop working first, add publishing later.

---

## 0. Have these ready (5 min)

- A Linux box (Pi 5, mini-PC, or VPS) with Node 20+ and Python 3.11+
- A Telegram account on your phone
- A **dedicated** Gmail account with 2-Step Verification enabled
- 3 cities in your region with lat/lon
- Your state code(s) and NWS forecast office code(s)
  *(find your office at [weather.gov](https://www.weather.gov/) — click your area, the 3-letter code is in the URL)*

---

## 1. Install OpenClaw (3 min)

```bash
npm install -g openclaw
openclaw config       # accept defaults; pick a model provider when prompted
openclaw gateway start
openclaw gateway status   # should say "Runtime: running"
```

Turn off per-command approval prompts (you're the only operator):

```bash
openclaw config set tools.exec.ask off
openclaw config set tools.exec.security full
openclaw gateway restart
```

---

## 2. Create your Telegram bot (3 min)

1. Telegram → message **@BotFather** → `/newbot` → save the **token**.
2. Telegram → message **@userinfobot** → save your **numeric user ID**.

Wire the token into OpenClaw:

```bash
mkdir -p ~/.openclaw/credentials
echo "<your-bot-token>" > ~/.openclaw/credentials/telegram-bot-token.txt
chmod 600 ~/.openclaw/credentials/telegram-bot-token.txt
```

Edit `~/.openclaw/openclaw.json` and add (replace `<you>` and `<your-id>`):

```json
"channels": {
  "telegram": {
    "enabled": true,
    "tokenFile": "/home/<you>/.openclaw/credentials/telegram-bot-token.txt",
    "groups": { "*": { "requireMention": true } }
  }
},
"commands": { "ownerAllowFrom": ["telegram:<your-id>"] },
"bindings": [
  { "type": "route", "agentId": "main", "match": { "channel": "telegram" } }
]
```

Restart and test:

```bash
openclaw gateway restart
# Open Telegram, message your bot. It should reply.
```

---

## 3. Create a Gmail App Password (3 min)

1. Visit [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. Create one named "WeatherBot".
3. Save the 16-character password.

You'll drop it into `.env` in the next step.

---

## 4. Drop in this template (2 min)

```bash
cd ~/.openclaw/workspace
git clone <this-repo-url> weather-agent   # or: cp -r <unpacked-template> weather-agent
cd weather-agent
cp .env.example .env
nano .env    # fill in everything below
```

**Minimum `.env` to get the Daily Forecast bot working:**

```bash
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_CHAT_ID=<your numeric user ID>
TELEGRAM_APPROVER_IDS=<your numeric user ID>

GMAIL_SMTP_USER=yourbrandweatherbot@gmail.com
GMAIL_APP_PASSWORD=<16-char app password>
GMAIL_APPROVAL_RECIPIENTS=you@example.com

# Region — change these
WX_REGION_NAME=Tampa Bay
WX_NWS_OFFICES=TBW
WX_STATE_CODES=FL
WX_FORECAST_POINTS=Tampa:27.95,-82.46;StPete:27.77,-82.64;Clearwater:27.97,-82.80
WX_TIMEZONE=America/New_York
```

Leave Facebook variables blank for now.

---

## 5. Tell OpenClaw to scaffold it (10 min)

Open a chat with your OpenClaw bot (Telegram works great) and paste these **three prompts in order**, waiting for each to finish:

### Prompt A
```
Read ~/.openclaw/workspace/weather-agent/.env and confirm you can see
my region settings, Telegram, and Gmail credentials. Don't print
secrets — just confirm each variable is present.
```

### Prompt B
```
In ~/.openclaw/workspace/weather-agent, create a Python venv at .venv,
install requests + python-dateutil + python-dotenv + beautifulsoup4 +
pillow, and create the package src/weather/ with these modules:

- nws_client.py: get_forecast(lat,lon), get_active_alerts(state),
  get_office_afd(office). Always set User-Agent.
- approval_store.py: file-locked JSON store at state/approvals.json
  with new_pending(kind, draft_path, ttl_hours), get(id),
  mark_approved(id, by).
- telegram_client.py: send_message(chat_id, text).
- email_client.py: send(subject, body, to).

Write a quick smoke test that pulls the forecast for the first city
in WX_FORECAST_POINTS and prints the high/low for tomorrow. Run it.
```

### Prompt C
```
Now build the Daily Forecast bot. Create scripts/daily_forecast.py
that pulls forecasts for each WX_FORECAST_POINTS city and active
alerts for each WX_STATE_CODES, then drafts a friendly Facebook-ready
post in our brand voice and saves it to output/YYYY-MM-DD/draft.md.

Then create scripts/request_daily_forecast_approval.py that reads the
latest draft, registers a pending approval (prefix dfa_), and sends
the draft + approval ID to me via Telegram and email.

Run both scripts now end-to-end so I get the Telegram message.
```

---

## 6. Approve your first post (1 min)

You'll get a Telegram message like:

```
Daily Forecast Approval — dfa_a1b2c3d4

«draft text»

Reply: APPROVE dfa_a1b2c3d4
```

Right now there's no Facebook publisher wired, so this is the loop validation. **You've made it.**

To turn approvals into real Facebook posts, add the publisher and approval-router hook by following [`RUNBOOK_PROMPTS.md`](./RUNBOOK_PROMPTS.md) prompts **4** and **5**.

---

## 7. Schedule it daily

Tell OpenClaw:

```
Add two cron jobs in America/New_York timezone, isolated sessions:

1. "Daily Forecast Generator" at 06:30 daily — runs:
   cd ~/.openclaw/workspace/weather-agent && source .venv/bin/activate
   && python scripts/daily_forecast.py && python scripts/request_daily_forecast_approval.py --latest

2. "Daily Forecast Approval Checker" every 15 minutes — once you've
   built the publisher (RUNBOOK_PROMPTS.md prompt 5), wire this to
   check_daily_forecast_approval.py.

Show me the cron list when done.
```

That's it. From here, work through `RUNBOOK_PROMPTS.md` to add the other bots one at a time.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Telegram bot doesn't respond | Check `openclaw gateway status`. Re-check the token file path in `openclaw.json`. |
| `403 Forbidden` from NWS | Add a real `User-Agent` header in `nws_client.py` (e.g. `WeatherBot (you@example.com)`). |
| Gmail SMTP auth failure | Confirm 2-Step Verification is on and you used the **App Password**, not your Google login password. |
| OpenClaw asking for `/approve` on every command | You skipped `tools.exec.ask off`. Re-run that command and restart the gateway. |
| No draft generated | Check `~/.openclaw/workspace/weather-agent/logs/` and look at the script output. Ask OpenClaw: *"Run daily_forecast.py and show me the full traceback if it fails."* |

---

## What's next

1. ✅ You did the quickstart — Daily Forecast loop works
2. ➡️ Add the **approval router hook** (RUNBOOK prompt 4) so your `APPROVE` replies actually do something
3. ➡️ Add **Facebook publishing** (RUNBOOK prompt 5)
4. ➡️ Add the other bots (RUNBOOK prompts 6–12)
5. ➡️ Run a final audit (RUNBOOK prompt 13)

Stay safe out there. ⛈️
