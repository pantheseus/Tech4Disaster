"""
Reusable LLM helper.

One function to remember:  analyze_report(text, image_bytes=None, media_type=None) -> dict
Plus generic helpers:      ask_llm(system, prompt) -> str     ask_json(system, prompt) -> dict

Providers (set LLM_PROVIDER in .env):
  groq       free tier, fast, OpenAI-compatible   (GROQ_API_KEY)
  gemini     free tier, supports images           (GEMINI_API_KEY)
  nvidia     NVIDIA NIM free credits              (NVIDIA_API_KEY)
  openai     paid                                 (OPENAI_API_KEY)
  anthropic  paid, Claude                         (ANTHROPIC_API_KEY)
  none       no API -> rule-based fallback so the demo NEVER breaks

If the API fails for any reason (no internet, rate limit), we fall back to the
rule-based analyzer, so your demo keeps working on stage.
"""
import base64
import json
import re
from typing import Optional

import requests

from . import config

# provider -> (base_url, key env var, default text model, default vision model)
OPENAI_COMPATIBLE = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY",
             "llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
               "gemini-2.5-flash", "gemini-2.5-flash"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY",
               "meta/llama-3.3-70b-instruct", "meta/llama-3.2-90b-vision-instruct"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini", "gpt-4o-mini"),
}
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-5-5"

import os

TIMEOUT = 40


def llm_enabled() -> bool:
    p = config.LLM_PROVIDER
    if p == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if p in OPENAI_COMPATIBLE:
        return bool(os.getenv(OPENAI_COMPATIBLE[p][1]))
    return False


def provider_info() -> dict:
    return {"provider": config.LLM_PROVIDER, "enabled": llm_enabled()}


# ---------------------------------------------------------------------------
# Low-level calls
# ---------------------------------------------------------------------------
def _call_openai_compatible(system: str, prompt: str, image_bytes, media_type) -> str:
    base, key_env, text_model, vision_model = OPENAI_COMPATIBLE[config.LLM_PROVIDER]
    has_image = image_bytes is not None
    model = (config.LLM_VISION_MODEL or vision_model) if has_image else (config.LLM_MODEL or text_model)

    if has_image:
        b64 = base64.b64encode(image_bytes).decode()
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{media_type or 'image/jpeg'};base64,{b64}"}},
        ]
    else:
        content = prompt

    r = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv(key_env)}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "temperature": 0.2,
            "max_tokens": 1000,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_anthropic(system: str, prompt: str, image_bytes, media_type) -> str:
    model = config.LLM_MODEL or ANTHROPIC_DEFAULT_MODEL
    content = []
    if image_bytes is not None:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": media_type or "image/jpeg",
            "data": base64.b64encode(image_bytes).decode()}})
    content.append({"type": "text", "text": prompt})
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.getenv("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": 1000, "system": system,
              "messages": [{"role": "user", "content": content}]},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")


def ask_llm(system: str, prompt: str, image_bytes: Optional[bytes] = None,
            media_type: Optional[str] = None) -> str:
    """Send a prompt (and optionally an image) to the configured LLM. Raises on failure."""
    if not llm_enabled():
        raise RuntimeError("LLM not configured")
    if config.LLM_PROVIDER == "anthropic":
        return _call_anthropic(system, prompt, image_bytes, media_type)
    return _call_openai_compatible(system, prompt, image_bytes, media_type)


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object in LLM output")
    return json.loads(text[start:end + 1])


def ask_json(system: str, prompt: str, image_bytes=None, media_type=None) -> dict:
    """Ask the LLM and parse the answer as JSON."""
    system = system + "\nRespond with ONLY a valid JSON object. No markdown, no explanation."
    return _extract_json(ask_llm(system, prompt, image_bytes, media_type))


# ---------------------------------------------------------------------------
# Disaster report triage
# ---------------------------------------------------------------------------
CATEGORIES = ["flood", "fire", "medical", "accident", "earthquake", "cyclone", "landslide", "infrastructure", "other"]

TRIAGE_SYSTEM = (
    "You are an emergency-response triage assistant for an Indian disaster-management control room. "
    "Read the citizen report (and photo if given) and return JSON with keys: "
    f"category (one of {CATEGORIES}), severity (integer 1-5, 5 = life-threatening), "
    "summary (max 20 words), suggested_action (max 25 words, concrete for responders), "
    "needs_immediate_rescue (true/false)."
)

_KEYWORDS = {
    "flood": ["flood", "water", "submerged", "inundat", "rain", "overflow", "river", "drown"],
    "fire": ["fire", "smoke", "burn", "blaze", "explosion"],
    "medical": ["injur", "bleed", "unconscious", "heart", "pregnan", "ambulance", "fracture", "hospital", "medicine"],
    "earthquake": ["earthquake", "quake", "tremor", "aftershock"],
    "cyclone": ["cyclone", "storm", "wind", "uprooted", "hurricane"],
    "landslide": ["landslide", "mudslide", "rockfall"],
    "accident": ["accident", "crash", "collision", "overturned", "lorry", "vehicle", "bike", "two-wheeler", "bus hit", "car hit"],
    "infrastructure": ["bridge", "road", "power", "electric", "pole", "building", "collapse", "tower"],
}
_SEVERE = ["trapped", "drowning", "unconscious", "collapsed", "bleeding", "child", "children",
           "elderly", "pregnant", "baby", "dying", "critical", "stuck", "missing", "fire"]

_ACTIONS = {
    "flood": "Dispatch boat/rescue team and move residents to the nearest shelter.",
    "fire": "Send fire tender immediately; evacuate adjacent buildings.",
    "medical": "Dispatch ambulance and alert the nearest hospital.",
    "earthquake": "Send search-and-rescue team; check for structural collapse.",
    "cyclone": "Issue shelter-in-place warning; clear fallen trees and power lines.",
    "landslide": "Block the road, send rescue team, check for people buried.",
    "accident": "Dispatch ambulance and police; clear the road and check for trapped passengers.",
    "infrastructure": "Send engineering team to secure the site and divert traffic.",
    "other": "Assign a field officer to verify the situation.",
}


def rule_based_triage(text: str) -> dict:
    t = text.lower()
    scores = {c: sum(k in t for k in kws) for c, kws in _KEYWORDS.items()}
    category = max(scores, key=scores.get) if max(scores.values()) > 0 else "other"
    severity = 2 + min(3, sum(w in t for w in _SEVERE))
    return {
        "category": category,
        "severity": severity,
        "summary": text.strip()[:110],
        "suggested_action": _ACTIONS[category],
        "needs_immediate_rescue": severity >= 4,
        "source": "rule-based",
    }


def analyze_report(text: str, image_bytes: Optional[bytes] = None,
                   media_type: Optional[str] = None) -> dict:
    """Main entry point. Always returns a dict with the keys documented in TRIAGE_SYSTEM."""
    if llm_enabled():
        try:
            data = ask_json(TRIAGE_SYSTEM, f"Citizen report: {text}", image_bytes, media_type)
            category = data.get("category", "other")
            if category not in CATEGORIES:
                category = "other"
            severity = max(1, min(5, int(data.get("severity", 3))))
            return {
                "category": category,
                "severity": severity,
                "summary": str(data.get("summary", text[:110])),
                "suggested_action": str(data.get("suggested_action", _ACTIONS[category])),
                "needs_immediate_rescue": bool(data.get("needs_immediate_rescue", severity >= 4)),
                "source": config.LLM_PROVIDER,
            }
        except Exception as e:  # network, rate limit, bad JSON ... never break the demo
            print(f"[llm] falling back to rule-based triage: {e}")
    return rule_based_triage(text)
