import json
import sys

import yaml

from agents.llm import call_json
from agents.utils import load_prompt, save_json


def run(brief, out_path="outputs/plan.json"):
    plan = call_json("planner", "planner_v1", load_prompt("planner_v1.txt"),
                     json.dumps(brief, ensure_ascii=False), output_path=out_path)
    save_json(plan, out_path)
    return plan


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        brief = yaml.safe_load(f)
    print(json.dumps(run(brief), indent=2))