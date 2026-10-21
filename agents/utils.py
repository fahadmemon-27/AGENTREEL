import json
import os
from pathlib import Path

from dotenv import load_dotenv
from PIL import ImageFont

load_dotenv()

W, H = 1080, 1920
END_CARD_S = 4
TEAM_ID = os.getenv("TEAM_ID", "T00")
DISCLOSURE = "Created with AI agents — LY Agentic AI Lab"


def load_prompt(name):
    return (Path("prompts") / name).read_text(encoding="utf-8")


def save_json(obj, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def font(size):
    for p in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines