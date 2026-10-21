import asyncio
import csv
import json
from pathlib import Path

import edge_tts
from moviepy import AudioFileClip
from PIL import Image, ImageDraw

from agents.logger import Timer, log_call
from agents.utils import DISCLOSURE, H, W, font, save_json, wrap

VOICE = "en-IN-NeerjaNeural"
OFFICIAL = Path("assets/official")
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


async def _tts(text, path):
    await edge_tts.Communicate(text, VOICE).save(str(path))


def ts(x):
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def chunk_captions(timings, n=6):
    caps = []
    for t in timings:
        words = t["text"].split()
        chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
        total = sum(len(c) for c in chunks) or 1
        cur, dur = t["start"], t["end"] - t["start"]
        for c in chunks:
            d = dur * len(c) / total
            caps.append({"start": round(cur, 2), "end": round(cur + d, 2), "text": c})
            cur += d
    return caps


def cover(img):
    r = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1))
    l, t = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((l, t, l + W, t + H))


def card_bg(i):
    palette = [(20, 40, 90), (120, 30, 60), (15, 90, 90), (70, 40, 120), (160, 80, 20), (30, 90, 50)]
    c = palette[i % len(palette)]
    img = Image.new("RGB", (W, H), c)
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(v * (1 - 0.6 * k)) for v in c))
    return img


def make_shot_image(shot, idx, photos, path):
    if photos:
        p = photos[idx % len(photos)]
        img = cover(Image.open(p).convert("RGB"))
        source, lic = str(p), "official media kit"
    else:
        img = card_bg(idx)
        source, lic = "generated (Pillow gradient card)", "own work"
    img = Image.alpha_composite(img.convert("RGBA"), Image.new("RGBA", (W, H), (0, 0, 0, 100))).convert("RGB")
    d = ImageDraw.Draw(img)
    f = font(88)
    y = 420  # below the top 250px unsafe zone
    for ln in wrap(d, shot["on_screen_text"], f, W - 200):
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill="white", stroke_width=3, stroke_fill="black")
        y += 110
    img.save(path)
    return source, lic


def make_end_card(brief, path):
    img = Image.new("RGB", (W, H), (15, 30, 70))
    d = ImageDraw.Draw(img)
    logos = [p for p in OFFICIAL.glob("*") if p.stem.lower().startswith("logo") and p.suffix.lower() in IMG_EXT]
    y = 520
    if logos:
        lg = Image.open(logos[0]).convert("RGBA")
        lg.thumbnail((700, 400))
        img.paste(lg, ((W - lg.width) // 2, y), lg)
        y += lg.height + 80
    else:
        f = font(110)
        w = d.textlength("SOMAIYA", font=f)
        d.text(((W - w) / 2, y), "SOMAIYA", font=f, fill="white")
        y += 200
    f = font(64)
    for ln in wrap(d, brief["cta"], f, W - 200):
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill="white")
        y += 85
    y += 80
    f2 = font(46)
    for ln in wrap(d, DISCLOSURE, f2, W - 200):
        w = d.textlength(ln, font=f2)
        d.text(((W - w) / 2, y), ln, font=f2, fill=(200, 200, 200))
        y += 62
    img.save(path)


def run(brief):
    script = json.load(open("outputs/script.json", encoding="utf-8"))
    sb = json.load(open("outputs/storyboard.json", encoding="utf-8"))
    for d in ("assets/audio", "assets/shots", "outputs"):
        Path(d).mkdir(parents=True, exist_ok=True)
    manifest = []

    # 1) voice-over, one file per segment (gives exact timings for captions)
    audio_files, timings, t = [], [], 0.0
    for i, s in enumerate(script["segments"], 1):
        p = Path(f"assets/audio/seg{i}.mp3")
        with Timer() as tm:
            asyncio.run(_tts(s["vo"], p))
        c = AudioFileClip(str(p))
        d = c.duration
        c.close()
        timings.append({"start": round(t, 2), "end": round(t + d, 2), "text": s["vo"]})
        t += d
        audio_files.append(str(p))
        manifest.append([str(p), f"Edge-TTS neural voice {VOICE}", "synthetic voice, no real person"])
        log_call("asset_generator", "tts", f"edge-tts:{VOICE}", "-", latency_s=tm.elapsed,
                 output_path=str(p), output_text=s["vo"], provider="edge-tts")
    body_s = round(t, 2)

    # 2) captions + SRT
    caps = chunk_captions(timings)
    with open("outputs/final.srt", "w", encoding="utf-8") as f:
        for i, c in enumerate(caps, 1):
            f.write(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n\n")

    # 3) shot images, durations rescaled to the real voice-over length
    photos = [p for p in sorted(OFFICIAL.glob("*"))
              if p.suffix.lower() in IMG_EXT and not p.stem.lower().startswith("logo")]
    raw = [max(s["end"] - s["start"], 1) for s in sb["shots"]]
    k = body_s / sum(raw)
    shots, cur = [], 0.0
    for i, (s, r) in enumerate(zip(sb["shots"], raw)):
        p = f"assets/shots/shot{i + 1}.png"
        src, lic = make_shot_image(s, i, photos, p)
        manifest.append([p, src, lic])
        end = body_s if i == len(raw) - 1 else round(cur + r * k, 2)
        shots.append({"image": p, "start": round(cur, 2), "end": end})
        cur = end

    # 4) end card
    make_end_card(brief, "assets/end_card.png")
    manifest.append(["assets/end_card.png", "generated (Pillow)", "own work; logo only if official file supplied"])

    with open("assets/manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "source", "licence"])
        w.writerows(manifest)

    save_json({"body_s": body_s, "shots": shots, "audio": audio_files, "captions": caps,
               "end_card": "assets/end_card.png", "end_text": DISCLOSURE},
              "outputs/timeline.json")
    return body_s


if __name__ == "__main__":
    import sys
    import yaml
    run(yaml.safe_load(open(sys.argv[1], encoding="utf-8")))
    print("assets ready")