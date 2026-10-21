import json
import re
from pathlib import Path

from moviepy import VideoFileClip

from agents.utils import TEAM_ID, save_json

RISKY = r"\b(ranked|ranking|rankings|rank|number one|placements?|packages?|lpa|crore|guaranteed?)\b"


def run(brief, out_path="outputs/qa_report.json"):
    final = Path(f"outputs/{TEAM_ID}_{brief['id']}_final.mp4")
    script = json.load(open("outputs/script.json", encoding="utf-8"))
    tl = json.load(open("outputs/timeline.json", encoding="utf-8"))
    facts = script["facts"]
    checks, feedback = [], None

    def add(name, ok, detail, route="scriptwriter"):
        checks.append({"check": name, "pass": bool(ok), "detail": detail, "route_to": route})

    if final.exists():
        v = VideoFileClip(str(final))
        dur, size, fps = v.duration, v.size, v.fps
        v.close()
        add("duration 30-60s", 30 <= dur <= 60, f"{dur:.1f}s")
        add("resolution 1080x1920", list(size) == [1080, 1920], str(size), "editor")
        add("frame rate 25/30", round(fps) in (25, 30), f"{fps}", "editor")
        add("file size <= 100MB", final.stat().st_size <= 100 * 1024 * 1024, f"{final.stat().st_size / 1e6:.1f}MB", "editor")
        if dur > 60:
            feedback = f"Last video was {dur:.0f}s, over the 60s limit. Make the script about 15% shorter."
        elif dur < 30:
            feedback = f"Last video was {dur:.0f}s, under 30s. Make the script about 25% longer."
    else:
        add("final video exists", False, str(final), "editor")

    add("subtitles .srt exists", Path("outputs/final.srt").exists(), "outputs/final.srt", "editor")
    add("AI disclosure on end card", "Created with AI agents" in tl.get("end_text", ""), tl.get("end_text", ""), "editor")

    body = [s for s in script["segments"] if s["type"] == "body"]
    add("facts were retrieved", len(facts) >= 3, f"{len(facts)} facts", "researcher")
    add("script has body segments", len(body) >= 1, f"{len(body)} body segments", "scriptwriter")
    add("every body segment cites a fact", bool(body) and all(s["fact_ids"] for s in body), "fact_ids present")
    add("all facts have source + page", bool(facts) and all(f.get("source") and f.get("page") for f in facts), f"{len(facts)} facts")

    corpus = (" ".join(f["claim"] + " " + f["quote"] for f in facts) + " " + brief["cta"]).lower().replace(",", "")
    vo = " ".join(s["vo"] for s in script["segments"])
    nums = [n.strip(".").replace(",", "") for n in re.findall(r"\d[\d,\.]*", vo)]
    bad_nums = [n for n in nums if n and n not in corpus]
    add("numbers in script appear in facts", not bad_nums, f"unverified: {bad_nums}" if bad_nums else "ok")

    risky = [m.group(0) for m in re.finditer(RISKY, vo.lower()) if m.group(0) not in corpus]
    add("no unverified ranking/placement words", not risky, f"found: {risky}" if risky else "ok")

    failed = [c for c in checks if not c["pass"]]
    if failed and not feedback:
        feedback = "Critic failed: " + "; ".join(f"{c['check']} ({c['detail']})" for c in failed)
    report = {"pass": not failed, "checks": checks, "feedback": feedback,
              "route_to": failed[0]["route_to"] if failed else None}
    save_json(report, out_path)
    for c in checks:
        print(("PASS " if c["pass"] else "FAIL ") + c["check"] + " - " + c["detail"])
    return report