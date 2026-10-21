import argparse
import random
import time

import yaml

from agents import (asset_generator, critic, editor, planner, researcher,
                    scriptwriter, storyboarder)
from agents.logger import set_run_id
from agents.utils import TEAM_ID


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    random.seed(a.seed)

    brief = yaml.safe_load(open(a.brief, encoding="utf-8"))
    set_run_id(f"{TEAM_ID}-{brief['id']}-{time.strftime('%m%d%H%M')}")

    print("Planner...");    planner.run(brief)
    print("Researcher..."); researcher.run(brief)

    feedback = None
    for loop in range(1, 4):  # critic loop, max 3
        print(f"--- Attempt {loop} ---")
        print("Scriptwriter...");     scriptwriter.run(brief, feedback=feedback)
        print("Storyboarder...");     storyboarder.run(brief)
        print("Asset generator...");  asset_generator.run(brief)
        print("Editor...");           editor.run(brief)
        print("Critic...")
        report = critic.run(brief)
        if report["pass"]:
            print("QA PASSED. Output is in outputs/")
            return
        feedback = report["feedback"]
        print("QA failed, looping back with feedback:", feedback)
    print("Stopped after 3 loops. See outputs/qa_report.json")


if __name__ == "__main__":
    main()