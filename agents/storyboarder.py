import json
import sys

import yaml

from agents.llm import call_json
from agents.utils import END_CARD_S, load_prompt, save_json


def normalise(shots, total):
    """Rescale shot durations so they exactly fill the body time."""
    raw = [max(s["end"] - s["start"], 1) for s in shots]
    k = total / sum(raw)
    t = 0.0
    for s, d in zip(shots, raw):
        s["start"] = round(t, 1)
        t += d * k
        s["end"] = round(t, 1)
        s["duration"] = round(s["end"] - s["start"], 1)
    shots[-1]["end"] = float(total)
    shots[-1]["duration"] = round(total - shots[-1]["start"], 1)
    return shots


def run(brief, script_path="outputs/script.json", out_path="outputs/storyboard.json"):
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    body_s = brief["duration_s"] - END_CARD_S
    user = json.dumps({"brief": brief, "script": script["segments"],
                       "body_duration_s": body_s}, ensure_ascii=False)
    sb = call_json("storyboarder", "storyboard_v1", load_prompt("storyboard_v1.txt"),
                   user, output_path=out_path)
    sb["shots"] = normalise(sb["shots"], body_s)
    save_json(sb, out_path)
    return sb


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        brief = yaml.safe_load(f)
    sb = run(brief)
    for s in sb["shots"]:
        print(f"{s['shot']}. [{s['start']}-{s['end']}s] {s['asset_source']}: "
              f"{s['visual']} | text: {s['on_screen_text']}")