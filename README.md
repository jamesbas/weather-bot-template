# OpenClaw Weather Bot Template

A complete, region-agnostic blueprint for building an AI-driven local weather operation on top of [OpenClaw](https://github.com/openclaw/openclaw) — modeled after **US Weather Warriors Delmarva**.

It pulls official **NWS / SPC / WPC** data, drafts public posts in your brand voice using an LLM (with a deterministic safety-net generator as fallback), and **only publishes after you reply `APPROVE <id>` on Telegram or email**. Optional second publish target: your own website via an HMAC-signed POST endpoint.

> **Reflects production lessons through 2026-05-17.** Includes the systemd-vs-OpenClaw-cron scheduling split, LLM-writer + deterministic fallback architecture, approval idempotency guard, and dual-target (Facebook + website) publishing.

## What's inside

| File | What it's for |
|---|---|
| [`QUICKSTART.md`](./QUICKSTART.md) | ⚡ Get one bot drafting posts in 30 minutes — start here |
| [`SETUP_GUIDE.md`](./SETUP_GUIDE.md) | Full reference: install OpenClaw, connect Telegram + Gmail + Facebook, project layout, **production patterns** (LLM writer, systemd timers, idempotency, website integration), security |
| [`RUNBOOK_PROMPTS.md`](./RUNBOOK_PROMPTS.md) | Copy/paste prompts to feed OpenClaw, in order, to scaffold every bot |
| `.env.example` | Template environment file (Telegram, Gmail, Facebook, optional website, region settings) |

## Recommended path

1. **New here?** Run [`QUICKSTART.md`](./QUICKSTART.md) (~30 min) to get one working bot end-to-end.
2. Skim [`SETUP_GUIDE.md`](./SETUP_GUIDE.md) for the architecture and the bits the quickstart skips (Facebook publishing, approval router hook, security, **and the production patterns section**).
3. Open [`RUNBOOK_PROMPTS.md`](./RUNBOOK_PROMPTS.md) and paste prompts 0 → 16 into your OpenClaw chat one at a time to add every other bot.
4. End state: ~10 weather bots running, gated by your Telegram approval, in an afternoon.

## What you get when you're done

- Daily Forecast bot (morning + afternoon)
- Severe Weather bot
- Alert Explainer bot (with maps)
- Storm Reports bot
- MarineCast bot (skip if inland)
- GrowCast bot (seasonal)
- Forecaster Briefing (private)
- Chase Target Advisor (private)
- Sounding Email Analyst (private utility)
- **Event Weather Advisor** (per-customer paid workflow, optional)
- Optional **website publishing** as a second target alongside Facebook

## Adapting to your region

The whole template is parameterized by environment variables — see the *Adapting this to your region* section in `SETUP_GUIDE.md`. Works anywhere in the US. For non-US regions, swap the data clients (Open-Meteo, Met Office, EnvCanada, BOM).

## Credit

Built by [US Weather Warriors](https://github.com/) — covering the Delmarva Peninsula. If you fork this, a link back is appreciated. Pull requests welcome.

⛈️ Stay safe out there.
