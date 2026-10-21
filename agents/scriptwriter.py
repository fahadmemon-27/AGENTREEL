import json
import sys

import yaml

from agents.llm import call_json
from agents.utils import END_CARD_S, load_prompt, save_json

WPS = 2.3  # spoken words per second


def run(brief, facts_path="outputs/facts.json",
        out_json="outputs/script.json", out_md="outputs/script.md", feedback=None):
    with open(facts_path, encoding="utf-8") as f:
        facts = json.load(f)["facts"]
    for i, f in enumerate(facts, 1):
        f["id"] = f"F{i}"
    body_s = brief["duration_s"] - END_CARD_S
    target = int(body_s * WPS)
    system = load_prompt("script_v1.txt")
    payload = {"brief": brief, "facts": facts,
               "body_duration_s": body_s, "target_words": target}
    if feedback:
        payload["feedback_from_critic"] = feedback
    user = json.dumps(payload, ensure_ascii=False)

    for attempt in range(3):
        script = call_json("scriptwriter", "script_v1", system, user,
                           output_path=out_json)
        words = sum(len(s["vo"].split()) for s in script["segments"])
        if 0.8 * target <= words <= 1.2 * target:
            break
        user += f"\nPrevious attempt had {words} words. Aim for {target}."

    valid = {f["id"] for f in facts}
    for s in script["segments"]:
        s["fact_ids"] = [x for x in s.get("fact_ids", []) if x in valid]
    script["facts"] = facts
    save_json(script, out_json)

    lines = [f"# Script - {brief['id']} ({brief['duration_s']}s)\n"]
    for s in script["segments"]:
        lines.append(f"[{s['start']:.0f}-{s['end']:.0f}s] ({s['type']}) {s['vo']}  "
                     f"<{', '.join(s['fact_ids'])}>")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return script


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        brief = yaml.safe_load(f)
    run(brief)
    print(open("outputs/script.md", encoding="utf-8").read())