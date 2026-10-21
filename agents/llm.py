import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from agents.logger import log_call

load_dotenv()

PROVIDERS = [
    {
        "name": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key": os.getenv("GEMINI_API_KEY"),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "in_rate": 0,
        "out_rate": 0,
        "use_seed": False,
    },
    {
        "name": "ollama",
        "base_url": "http://localhost:11434/v1",
        "key": "ollama",
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        "in_rate": 0,
        "out_rate": 0,
        "use_seed": True,
    },
]


def call_llm(agent, prompt_id, system, user, json_mode=False,
             temperature=0.4, seed=42, output_path=None):
    """Try Gemini first, fall back to local Ollama. Every call is logged."""
    last_error = None
    for p in PROVIDERS:
        if not p["key"]:
            continue
        client = OpenAI(base_url=p["base_url"], api_key=p["key"],
                        timeout=90 if p["name"] == "gemini" else 300, max_retries=1)
        kwargs = dict(
            model=p["model"],
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature,
        )
        if p.get("use_seed"):
            kwargs["seed"] = seed
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        t0 = time.time()
        try:
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            usage = resp.usage
            in_tok = usage.prompt_tokens if usage else 0
            out_tok = usage.completion_tokens if usage else 0
            cost = (in_tok * p["in_rate"] + out_tok * p["out_rate"]) / 1_000_000
            log_call(agent, "llm", p["model"], prompt_id, in_tok, out_tok, cost,
                     time.time() - t0, "ok", output_path, text, p["name"])
            return text
        except Exception as e:
            last_error = e
            log_call(agent, "llm", p["model"], prompt_id, latency_s=time.time() - t0,
                     status=f"error: {str(e)[:100]}", provider=p["name"])
    raise RuntimeError(f"All LLM providers failed: {last_error}")


def call_json(agent, prompt_id, system, user, **kw):
    """Same as call_llm but returns parsed JSON."""
    text = call_llm(agent, prompt_id, system, user, json_mode=True, **kw)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)