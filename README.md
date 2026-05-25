# OpenClaw Weather Bot Template

A complete, region-agnostic blueprint for building an AI-driven local weather operation on top of [OpenClaw](https://github.com/openclaw/openclaw) — modeled after **US Weather Warriors Delmarva**.

It pulls official **NWS / SPC / WPC** data, drafts public posts in your brand voice using an LLM (with a deterministic safety-net generator as fallback), and **only publishes after you reply `APPROVE <id>` on Telegram or email**. Optional second publish target: your own website via an HMAC-signed POST endpoint.

> **Reflects production lessons through 2026-05-25.** Includes the systemd-vs-OpenClaw-cron scheduling split, LLM-writer + deterministic fallback architecture, approval idempotency guard, dual-target (Facebook + website) publishing, the **auto-publish + FYI** pattern for trusted public bots (MarineCast + public GrowCast), the **Tropical Watch Bot** (NHC TWO monitor) with approval routing, and the **HREF × SPC × HRRR synthesis** internal-briefing bot with HRRR cross-check.

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

- Daily Forecast bot (morning + afternoon, approval-gated)
- Severe Weather bot (approval-gated)
- Alert Explainer bot (with maps, approval-gated)
- Storm Reports bot (approval-gated)
- MarineCast bot (skip if inland) — **optional auto-publish + FYI** mode
- GrowCast bot (seasonal) — daily public can run **auto-publish + FYI**; private weekly grower briefing stays email-only
- **Tropical Watch bot** (NHC TWOs / NHC active storms, Delmarva-relevance filtered, approval-gated)
- **HREF × SPC × HRRR Synthesis** internal briefing (3× daily, private email + Telegram, no public posting)
- Forecaster Briefing (private)
- Chase Target Advisor (private, with dedup gate)
- Sounding Email Analyst (private utility, hybrid systemd-poll + OpenClaw-cron read-gated analyst)
- **Event Weather Advisor** (per-customer paid workflow, optional, with email-intake systemd timer)
- Optional **website publishing** as a second target alongside Facebook
- Mailbox cleanup (systemd timer, daily)

## Adapting to your region

The whole template is parameterized by environment variables — see the *Adapting this to your region* section in `SETUP_GUIDE.md`. Works anywhere in the US. For non-US regions, swap the data clients (Open-Meteo, Met Office, EnvCanada, BOM).

## Credit

Built by [US Weather Warriors](https://github.com/) — covering the Delmarva Peninsula. If you fork this, a link back is appreciated. Pull requests welcome.

⛈️ Stay safe out there.
