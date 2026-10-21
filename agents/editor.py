import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from moviepy import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                     ImageClip, concatenate_audioclips, concatenate_videoclips)
from PIL import Image, ImageDraw

from agents.logger import Timer, log_call
from agents.utils import END_CARD_S, H, TEAM_ID, W, font, wrap


def caption_png(text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(58)
    lines = wrap(d, text, f, W - 160)
    lh = 76
    y0 = 1300  # inside safe zone (above bottom 350px)
    d.rounded_rectangle((60, y0 - 20, W - 60, y0 - 20 + lh * len(lines) + 40),
                        radius=24, fill=(0, 0, 0, 170))
    y = y0
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill="white")
        y += lh
    img.save(path)


def shot_clip(path, dur):
    c = ImageClip(path).with_duration(dur)
    c = c.resized(lambda t: 1 + 0.06 * t / dur)  # slow zoom (Ken Burns)
    return CompositeVideoClip([c.with_position("center")], size=(W, H)).with_duration(dur)


def run(brief):
    tl = json.load(open("outputs/timeline.json", encoding="utf-8"))
    raw = Path("outputs/_raw.mp4")
    final = Path(f"outputs/{TEAM_ID}_{brief['id']}_final.mp4")
    Path("assets/captions").mkdir(parents=True, exist_ok=True)

    with Timer() as tm:
        body = concatenate_videoclips(
            [shot_clip(s["image"], s["end"] - s["start"]) for s in tl["shots"]],
            method="compose")
        caps = []
        for i, c in enumerate(tl["captions"], 1):
            p = f"assets/captions/cap{i}.png"
            caption_png(c["text"], p)
            caps.append(ImageClip(p).with_start(c["start"])
                        .with_duration(c["end"] - c["start"]).with_position((0, 0)))
        body = CompositeVideoClip([body] + caps, size=(W, H)).with_duration(tl["body_s"])
        end = ImageClip(tl["end_card"]).with_duration(END_CARD_S)
        video = concatenate_videoclips([body, end], method="compose")
        narr = concatenate_audioclips([AudioFileClip(f) for f in tl["audio"]])
        video = video.with_audio(CompositeAudioClip([narr]).with_duration(video.duration))
        video.write_videofile(str(raw), fps=30, codec="libx264", audio_codec="aac",
                              audio_fps=48000,
                              ffmpeg_params=["-pix_fmt", "yuv420p", "-profile:v", "high"])

    # loudness normalisation to about -14 LUFS, 48 kHz stereo AAC
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(raw),
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-ac", "2", "-movflags", "+faststart", str(final)], check=True)
    raw.unlink(missing_ok=True)
    log_call("editor", "moviepy+ffmpeg", "moviepy/loudnorm", "-", latency_s=tm.elapsed,
             output_path=str(final), provider="local")
    return str(final)


if __name__ == "__main__":
    import sys
    import yaml
    print(run(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))))