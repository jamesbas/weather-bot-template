"""Reference implementation of a USWW-style LLM writer with a deterministic
safety-net fallback.

Copy this file to ``src/weather/<bot>_writer.py`` and customize the
``SYSTEM_PERSONA``, ``HARD_RULES``, ``OUTPUT_TEMPLATE``, and ``build_prompt(...)``
function for your specific bot. The CLI bridge and dataclass shape stay the
same across every bot.

Every production USWW writer follows this exact pattern. See
``PROMPTS_REFERENCE.md`` for the prompt text used by each of the seven
production bots.

Usage (in your bot's generator script):

    from weather.example_writer import ExampleWriter, build_prompt

    writer = ExampleWriter()             # defers to gateway default model
    prompt = build_prompt(source=...)
    text, llm_used, fallback_reason = writer.write_post(
        prompt=prompt,
        fallback=lambda: deterministic_render(...),
    )

    # Always save artifacts so failures are diagnosable:
    Path("output/example_llm_prompt.txt").write_text(prompt)
    Path("output/example_llm_meta.json").write_text(json.dumps({
        "llm_used": llm_used,
        "fallback_reason": fallback_reason,
        "model": writer.model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }))
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------
# When None, the writer omits ``--model`` from the CLI call and defers to the
# OpenClaw gateway default. This is the recommended default — keeps the bot
# decoupled from any specific provider/model.
#
# Override per-bot via the writer dataclass ``model`` field if you need to
# pin one (e.g. send the Forecaster Briefing to a larger model than the
# daily post).
DEFAULT_MODEL: "str | None" = None


# ---------------------------------------------------------------------------
# Prompt strings — REPLACE THESE PER BOT
# ---------------------------------------------------------------------------

SYSTEM_PERSONA = (
    "You are the EXAMPLE Weather writer for EXAMPLE_REGION. Voice is calm, "
    "specific, and grounded. No padding, no hedging clichés, no 'always "
    "check official sources' filler."
)


HARD_RULES = """\
HARD RULES (do not violate):
1. Use ONLY the numbers, alerts, and SPC/WPC/AFD signals in the SOURCE DATA
   block below. Do not invent temperatures, alert types, severe risk levels,
   or rainfall amounts.
2. Do NOT downgrade or upgrade SPC severe risk language. Reproduce
   "Marginal", "Slight", "Enhanced", "Moderate", "High", and "PDS"
   verbatim from the source.
3. Use °F and mph; convert if metric appears in source.
4. Cite specific cities/areas where source data provides them.
5. Emojis: a single weather-appropriate emoji in the header only. No emojis
   elsewhere.
6. Hashtags: only `#EXAMPLEWeather #EXAMPLEStateWx` at the very bottom.
7. Total length: 250–400 words. Tight, useful, every sentence earns its
   place.
8. End with "— EXAMPLE Weather 🌪️" on its own line ABOVE the hashtags.
9. If SOURCE DATA has missing or null fields for a section, omit that
   section silently. Do not write "no data available".
10. Do not output markdown fences, JSON, preamble, or commentary.
"""


OUTPUT_TEMPLATE = """\
OUTPUT TEMPLATE (follow exactly; one blank line between sections):

{emoji} EXAMPLE Weather Update — {forecast_date}

{{one-sentence headline tied to the dominant weather story today}}

Today's Weather Story:
{{2–4 sentences. The dominant weather narrative.}}

Across the Region:
{{bullet list, one per sampled point: city, sky/condition, high temp, wind.}}

Bottom Line:
{{ONE sentence verdict.}}

— EXAMPLE Weather 🌪️
#EXAMPLEWeather #EXAMPLEStateWx
"""


# ---------------------------------------------------------------------------
# Source-data → YAML helper
# ---------------------------------------------------------------------------
# Renders structured data as YAML-ish indented text. Not strict YAML —
# readability for the model wins. Truncates runaway strings so a giant AFD
# doesn't blow the context window.

def _yaml_safe(value: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if value is None or value == "":
        return f"{pad}null"
    if isinstance(value, (int, float, bool)):
        return f"{pad}{value}"
    if isinstance(value, str):
        s = value.strip().replace("\r", "")
        if "\n" in s:
            # Block scalar so the model sees full text without truncation.
            inner = "\n".join(f"{pad}  {line}" for line in s.splitlines())
            return f"{pad}|\n{inner}"
        if len(s) > 1200:
            s = s[:1200].rstrip(" .,") + "…"
        return f"{pad}{s}"
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                lines.append(_yaml_safe(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {_yaml_safe(v, 0).strip()}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(_yaml_safe(item, indent + 1))
            else:
                lines.append(f"{pad}- {_yaml_safe(item, 0).strip()}")
        return "\n".join(lines)
    return f"{pad}{value!r}"


# ---------------------------------------------------------------------------
# build_prompt — customize per bot
# ---------------------------------------------------------------------------

def build_prompt(*, source: dict[str, Any]) -> str:
    """Build the full LLM prompt for one run.

    Pass in the deterministic source-data dict your bot already builds for
    its fallback generator. Keep this function pure and side-effect-free
    so it's easy to snapshot the prompt for tests/debugging.
    """
    # Pick the header emoji deterministically from the source data, NOT
    # from the LLM. Stops the model from drifting on the visual signal.
    emoji = _pick_emoji(source)

    return (
        SYSTEM_PERSONA
        + "\n\n"
        + HARD_RULES
        + "\n\n"
        + OUTPUT_TEMPLATE
        + f"\nHEADER EMOJI FOR THIS POST: {emoji}\n"
        + "\nSOURCE DATA:\n"
        + _yaml_safe(source)
        + "\n\nNow write the post using the template above. Only output the "
          "post text — no preamble, no JSON, no markdown fences. If you are "
          "uncertain about any fact, omit it rather than guess.\n"
    )


def _pick_emoji(source: dict[str, Any]) -> str:
    """Deterministic header-emoji selection — customize per bot."""
    if any(a.get("event", "").lower().startswith("tornado")
           for a in source.get("alerts", []) or []):
        return "🌪️"
    if source.get("severe_potential_level") in ("high", "moderate"):
        return "⛈️"
    if source.get("dominant_story") == "heat":
        return "🥵"
    if source.get("dominant_story") == "cold":
        return "❄️"
    return "🌤️"


# ---------------------------------------------------------------------------
# LLM CLI bridge
# ---------------------------------------------------------------------------
# Shells out to the OpenClaw model CLI, parses the JSON envelope, and
# returns a (ok, text, error_reason) tuple. Never raises.

def _run_cli(prompt: str, model: "str | None", timeout: int) -> tuple[bool, str, str]:
    cli = shutil.which("openclaw") or "openclaw"
    cmd = [cli, "capability", "model", "run", "--prompt", prompt]
    if model:
        cmd += ["--model", model]
    cmd += ["--gateway", "--json"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", "cli_timeout"
    except FileNotFoundError:
        return False, "", "cli_missing"
    except Exception as exc:
        return False, "", f"cli_error: {exc}"

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] \
            or ["nonzero_exit"]
        return False, "", f"cli_exit_{proc.returncode}: {err[0]}"

    raw = (proc.stdout or "").strip()
    if not raw:
        return False, "", "empty_stdout"

    try:
        data = json.loads(raw)
    except Exception as exc:
        return False, "", f"json_parse: {exc}"

    if not data.get("ok"):
        return False, "", f"cli_not_ok: {data.get('error') or 'no_error_field'}"

    outputs = data.get("outputs") or []
    if not outputs:
        return False, "", "no_outputs"

    text = (outputs[0] or {}).get("text", "")
    if not text or not text.strip():
        return False, "", "empty_text"

    return True, text.strip() + "\n", ""


# ---------------------------------------------------------------------------
# Writer dataclass — the public API
# ---------------------------------------------------------------------------

@dataclass
class ExampleWriter:
    """LLM writer with a deterministic safety-net fallback.

    Attributes
    ----------
    model:
        Provider/model override (e.g. ``"openai/gpt-4o-mini"``). Leave as
        ``None`` to defer to the OpenClaw gateway default.
    timeout:
        Subprocess timeout in seconds. 90s is plenty for public posts;
        120s for the Forecaster Briefing.
    cli_runner:
        Optional injection point for tests — match the signature of
        ``_run_cli``. Defaults to the real CLI.
    """

    model: "str | None" = DEFAULT_MODEL
    timeout: int = 90
    cli_runner: Callable[[str, "str | None", int], tuple[bool, str, str]] | None = None

    def _run(self, prompt: str) -> tuple[bool, str, str]:
        runner = self.cli_runner or _run_cli
        return runner(prompt, self.model, self.timeout)

    def write_post(
        self,
        *,
        prompt: str,
        fallback: Callable[[], str],
        errors: list[str] | None = None,
    ) -> tuple[str, bool, "str | None"]:
        """Run the LLM; on ANY failure, return the deterministic fallback.

        Returns a 3-tuple ``(text, llm_used, fallback_reason)``:

        * ``text`` — the post body (LLM output on success, deterministic on
          fallback).
        * ``llm_used`` — ``True`` if the LLM call succeeded; ``False`` if we
          fell back.
        * ``fallback_reason`` — short error tag (``"cli_timeout"``,
          ``"empty_text"``, ``"cli_not_ok: …"``, …) or ``None`` on success.

        Reasons we fall back:

        1. CLI not on ``$PATH``.
        2. Subprocess timeout.
        3. Non-zero CLI exit code.
        4. Empty stdout.
        5. JSON parse failure on the envelope.
        6. ``ok != True`` in the envelope.
        7. No ``outputs[0].text`` or empty text.
        """
        ok, text, err = self._run(prompt)
        if ok:
            return text, True, None

        reason = err or "unknown"
        if errors is not None:
            errors.append(f"example_writer fallback ({reason})")
        return fallback(), False, reason


# ---------------------------------------------------------------------------
# Companion file — scripts/test_<bot>_writer.py — sketch
# ---------------------------------------------------------------------------
#
# Every production writer ships with a smoke test covering four cases:
#
#   1. build_prompt produces a string containing each HARD_RULE bullet and
#      every key field from the source bundle.
#   2. Success path: a mocked cli_runner returns a valid envelope, the
#      writer returns (text, True, None).
#   3. Subprocess-error fallback: the mocked cli_runner raises / returns
#      "cli_timeout"; the writer returns the deterministic fallback and
#      llm_used == False.
#   4. Non-OK envelope fallback: the mocked cli_runner returns
#      (False, "", "cli_not_ok: …"); the writer falls back cleanly.
#
# Skeleton:
#
#   from weather.example_writer import ExampleWriter, build_prompt
#
#   def test_prompt_contents():
#       prompt = build_prompt(source={"forecast_date": "2026-05-18", ...})
#       assert "HARD RULES" in prompt
#       assert "2026-05-18" in prompt
#       assert "SOURCE DATA:" in prompt
#
#   def test_success_path():
#       def fake_runner(p, m, t): return True, "fake post\n", ""
#       w = ExampleWriter(cli_runner=fake_runner)
#       text, llm_used, reason = w.write_post(
#           prompt="x", fallback=lambda: "FALLBACK")
#       assert text == "fake post\n"
#       assert llm_used is True
#       assert reason is None
#
#   def test_subprocess_error_fallback():
#       def fake_runner(p, m, t): return False, "", "cli_timeout"
#       w = ExampleWriter(cli_runner=fake_runner)
#       text, llm_used, reason = w.write_post(
#           prompt="x", fallback=lambda: "FALLBACK")
#       assert text == "FALLBACK"
#       assert llm_used is False
#       assert reason == "cli_timeout"
#
#   def test_non_ok_envelope_fallback():
#       def fake_runner(p, m, t): return False, "", "cli_not_ok: bad"
#       w = ExampleWriter(cli_runner=fake_runner)
#       text, llm_used, reason = w.write_post(
#           prompt="x", fallback=lambda: "FALLBACK")
#       assert text == "FALLBACK"
#       assert llm_used is False
#       assert reason.startswith("cli_not_ok")
