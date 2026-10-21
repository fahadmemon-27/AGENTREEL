import csv
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
RUN_LOG = LOG_DIR / "run_log.jsonl"
COST_CSV = LOG_DIR / "cost_report.csv"
INTERVENTIONS = LOG_DIR / "interventions.md"

_run_id = "T00-B06-01"


def set_run_id(run_id: str):
    global _run_id
    _run_id = run_id


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def log_call(agent, tool, model, prompt_id, input_tokens=0, output_tokens=0,
             cost_inr=0.0, latency_s=0.0, status="ok", output_path=None,
             output_text="", provider="", human_intervention=False):
    LOG_DIR.mkdir(exist_ok=True)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "run_id": _run_id,
        "agent": agent,
        "tool": tool,
        "provider": provider,
        "model": model,
        "prompt_id": prompt_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_inr": round(cost_inr, 4),
        "latency_s": round(latency_s, 2),
        "status": status,
        "output_path": output_path,
        "output_sha256": sha256_text(output_text) if output_text else None,
        "human_intervention": human_intervention,
    }
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    new_file = not COST_CSV.exists() or COST_CSV.stat().st_size == 0
    with open(COST_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["stage", "provider", "model", "input_tokens",
                        "output_tokens", "cost_inr"])
        w.writerow([agent, provider, model, input_tokens, output_tokens,
                    round(cost_inr, 4)])


def log_intervention(stage, change, reason):
    """Call this whenever a human edits something during the Live Run."""
    LOG_DIR.mkdir(exist_ok=True)
    new_file = not INTERVENTIONS.exists() or INTERVENTIONS.stat().st_size == 0
    with open(INTERVENTIONS, "a", encoding="utf-8") as f:
        if new_file:
            f.write("| Time | Stage / agent | What the human changed | Reason |\n")
            f.write("|---|---|---|---|\n")
        f.write(f"| {datetime.now().strftime('%H:%M')} | {stage} | {change} | {reason} |\n")


class Timer:
    def __enter__(self):
        self.t = time.time()
        return self

    def __exit__(self, *a):
        self.elapsed = time.time() - self.t