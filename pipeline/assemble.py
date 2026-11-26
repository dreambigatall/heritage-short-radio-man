"""Stage: assembly. Deterministic FFmpeg edit, driven entirely by storyboard.json and the
manifests of the earlier stages. No model calls happen here.

Shot timing is set by the narration: a shot lasts max(duration_s, lead + narration + pad).
Then, for each aspect ratio:  per-shot segments (Ken Burns, clip or black) -> concat ->
burn ASS subtitles -> mux with the mix (narration + ducked score, loudness-normalised).

Reads:  storyboard.json, outputs/{narration,shots,music}/manifest.json
Writes: outputs/edit/... (segments, mix, subtitles, timeline.json), outputs/film/*.mp4 and *.srt
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import (ROOT, ffmpeg, ffmpeg_stderr, input_hash, load_storyboard, media_duration, outdir,
                    read_manifest, rel, resolution)

ASPECTS = ("9x16", "16x9")
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


# ---------------------------------------------------------------- timing

def build_timeline(sb: dict, narr: dict) -> list[dict]:
    fps = sb["output"]["fps"]
    lead = sb["output"].get("narration_lead_s", 0.3)
    pad = sb["output"].get("narration_pad_s", 0.6)
    t = 0.0
    timeline = []
    for shot in sb["shots"]:
        sid = shot["id"]
        if shot["narration"].strip() and sid not in narr:
            raise SystemExit(f"{sid}: no narration audio. Run `python run.py narration` first.")
        nd = narr.get(sid, {}).get("duration_s", 0.0)
        want = max(shot["duration_s"], (lead + nd + pad) if nd else 0)
        frames = round(want * fps)
        d = frames / fps
        timeline.append({"shot": sid, "start": round(t, 3), "duration": round(d, 3), "frames": frames,
                         "narration_s": nd, "narration_file": narr.get(sid, {}).get("file"),
                         "subtitle": shot["subtitle_en"], "lead": lead})
        t += d
    return timeline


# ---------------------------------------------------------------- picture

def kenburns_filter(camera: str, w: int, h: int, frames: int, fps: int) -> str:
    n = max(frames - 1, 1)
    p = f"(on/{n})"
    zoom = {"push_in": f"1+0.12*{p}", "pull_out": f"1.12-0.12*{p}", "static": "1.03",
            "pan_left": "1.12", "pan_right": "1.12", "tilt_up": "1.12", "tilt_down": "1.12"}[camera]
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    x = {"pan_left": f"(iw-iw/zoom)*(1-{p})", "pan_right": f"(iw-iw/zoom)*{p}"}.get(camera, cx)
    y = {"tilt_up": f"(ih-ih/zoom)*(1-{p})", "tilt_down": f"(ih-ih/zoom)*{p}"}.get(camera, cy)
    # crop the (square) keyframe to the target aspect, upscale so zoompan's integer steps don't jitter
    return (f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})':'(iw-ow)/2':'(ih-oh)*0.3',scale={w * 3}:{h * 3}:flags=lanczos,"
            f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},setsar=1,format=yuv420p")


def render_segment(src: dict | None, item: dict, w: int, h: int, fps: int, seg_dir: Path) -> Path:
    frames = item["frames"]
    kind = "black" if src is None else src["type"]
    key = {"kind": kind, "src": src, "frames": frames, "w": w, "h": h, "fps": fps, "v": 3}
    path = seg_dir / f"{item['shot']}_{input_hash(key)}.mp4"
    if path.exists():
        return path
    if kind == "black":
        ffmpeg(["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}", "-frames:v", str(frames), *ENC, str(path)])
    elif kind == "kenburns":
        ffmpeg(["-i", str(ROOT / src["file"]), "-vf", kenburns_filter(src["camera"], w, h, frames, fps),
                "-frames:v", str(frames), *ENC, str(path)])
    else:  # generated clip: drop the weak first 0.25 s, slow it down up to 1.5x if short, then hold last frame
        usable = max(media_duration(ROOT / src["file"]) - 0.25, 0.5)
        stretch = min(max(frames / fps / usable, 1.0), 1.5)
        vf = (f"trim=start=0.25,setpts={stretch:.4f}*(PTS-STARTPTS),fps={fps},"
              f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,"
              f"tpad=stop_mode=clone:stop_duration=30,format=yuv420p")
        ffmpeg(["-i", str(ROOT / src["file"]), "-an", "-vf", vf, "-frames:v", str(frames), *ENC, str(path)])
    return path


def _font(size: int):
    from PIL import ImageFont

    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(draw, text: str, font, max_w: int) -> list[str]:
    words, out, cur = text.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if cur and draw.textbbox((0, 0), trial, font=font)[2] > max_w:
            out.append(cur)
            cur = wd
        else:
            cur = trial
    return out + ([cur] if cur else [])


def render_end_card(sb: dict, w: int, h: int, fps: int, seg_dir: Path) -> tuple[Path, float]:
    from PIL import Image, ImageDraw

    card = sb["end_card"]
    d = card["duration_s"]
    frames = round(d * fps)
    key = {"lines": card["lines"], "w": w, "h": h, "frames": frames, "v": 2}
    h_ = input_hash(key)
    path = seg_dir / f"endcard_{h_}.mp4"
    if path.exists():
        return path, frames / fps
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    big, small = _font(int(min(w, h) * 0.075)), _font(int(min(w, h) * 0.032))
    lines = [(card["lines"][0], big)]
    for t in card["lines"][1:]:  # wrap credits so nothing runs off a 9:16 frame
        for part in _fit(draw, t, small, int(w * 0.86)):
            lines.append((part, small))
    heights = [draw.textbbox((0, 0), t, font=f)[3] for t, f in lines]
    y = (h - sum(heights) - 30 * (len(lines) - 1)) / 2
    for (text, font), lh in zip(lines, heights):
        tw = draw.textbbox((0, 0), text, font=font)[2]
        draw.text(((w - tw) / 2, y), text, font=font, fill=(240, 230, 210))
        y += lh + 30
    png = seg_dir / f"endcard_{h_}.png"
    img.save(png)
    ffmpeg(["-loop", "1", "-i", str(png), "-vf", f"fps={fps},fade=t=in:d=0.5,format=yuv420p",
            "-frames:v", str(frames), *ENC, str(path)])
    return path, frames / fps


def concat(segments: list[Path], out: Path) -> None:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


# ---------------------------------------------------------------- sound

def build_narration_track(timeline: list[dict], tail: float, out: Path) -> None:
    args, filters, labels = [], [], []
    for i, item in enumerate(timeline):
        d = item["duration"]
        if item["narration_file"]:
            args += ["-i", str(ROOT / item["narration_file"])]
            ms = int(item["lead"] * 1000)
            filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms},apad,atrim=0:{d:.3f}[a{i}]")
        else:
            args += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
            filters.append(f"[{i}:a]atrim=0:{d:.3f}[a{i}]")
        labels.append(f"[a{i}]")
    n = len(timeline)
    args += ["-f", "lavfi", "-t", f"{tail:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
    labels.append(f"[{n}:a]")
    filters.append("".join(labels) + f"concat=n={n + 1}:v=0:a=1[out]")
    ffmpeg([*args, "-filter_complex", ";".join(filters), "-map", "[out]", str(out)])


def build_mix(narration: Path, music: Path, total: float, music_gain_db: float, out: Path) -> None:
    """Score ducked under the voice with sidechaincompress, then loudness-normalised to -14 LUFS / -1 dBTP."""
    fc = (
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={music_gain_db}dB,"
        f"atrim=0:{total:.3f},afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.3f}:d=3[m];"
        f"[0:a]aformat=channel_layouts=stereo,asplit=2[v][sc];"
        f"[m][sc]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[duck];"
        f"[v][duck]amix=inputs=2:duration=first:normalize=0,"
        f"loudnorm=I=-14:TP=-1:LRA=11,aresample=48000[out]"
    )
    ffmpeg(["-i", str(narration), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex", fc, "-map", "[out]", "-t", f"{total:.3f}", str(out)])


def measure_loudness(path: Path) -> dict:
    err = ffmpeg_stderr(["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return {"integrated_lufs": float(i.group(1)) if i else None, "true_peak_dbfs": float(tp.group(1)) if tp else None}


# ---------------------------------------------------------------- subtitles

def _wrap(text: str, width: int = 40) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > width:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}".strip()
    if cur:
        lines.append(cur)
    return lines


def subtitle_cues(timeline: list[dict], width: int = 40) -> list[tuple[float, float, list[str]]]:
    """At most two lines of `width` characters per cue; longer lines are split across cues in proportion to length."""
    cues = []
    for it in timeline:
        if not it["subtitle"].strip():
            continue
        start = it["start"] + it["lead"]
        end = start + it["narration_s"] if it["narration_s"] else it["start"] + it["duration"] - 0.2
        end = min(end + 0.25, it["start"] + it["duration"] - 0.05)
        lines = _wrap(it["subtitle"], width)
        chunks = [lines[i:i + 2] for i in range(0, len(lines), 2)]
        total_chars = sum(len(" ".join(c)) for c in chunks)
        t = start
        for c in chunks:
            span = (end - start) * len(" ".join(c)) / total_chars
            cues.append((t, t + span, c))
            t += span
    return cues


def _ts(t: float, sep: str) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    if sep == ",":
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_srt(cues, path: Path) -> None:
    out = [f"{i}\n{_ts(a, ',')} --> {_ts(b, ',')}\n" + "\n".join(lines) + "\n"
           for i, (a, b, lines) in enumerate(cues, 1)]
    path.write_text("\n".join(out), encoding="utf-8")


def write_ass(cues, w: int, h: int, path: Path) -> None:
    vertical = h > w
    fs = int(w * 0.045) if vertical else int(h * 0.052)
    mv = int(h * 0.16) if vertical else int(h * 0.07)      # keep clear of phone UI in 9:16
    ml = int(w * 0.08)
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{fs},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,"
        f"{max(2, fs // 14)},1,2,{ml},{ml},{mv},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    body = "".join(
        f"Dialogue: 0,{_ts(a, '.')},{_ts(b, '.')},Default,,0,0,0,,"
        + "\\N".join(l.replace("{", "(").replace("}", ")") for l in lines) + "\n"
        for a, b, lines in cues)
    path.write_text(head + body, encoding="utf-8")


# ---------------------------------------------------------------- main

def run(radio: bool = False, aspects: tuple[str, ...] = ASPECTS) -> dict:
    sb = load_storyboard()
    fps, quality = sb["output"]["fps"], sb["output"]["quality"]
    narr = read_manifest("narration")
    shots = {} if radio else read_manifest("shots")
    music = read_manifest("music").get("score")
    if not music:
        raise SystemExit("No score resolved. Run `python run.py music` first.")
    if not radio:
        missing = [s["id"] for s in sb["shots"] if s["id"] not in shots]
        if missing:
            raise SystemExit(f"No picture for {', '.join(missing)}. Run keyframes and shots first.")

    edit, film = outdir("edit"), outdir("film")
    timeline = build_timeline(sb, narr)
    card_d = round(sb["end_card"]["duration_s"] * fps) / fps
    total = sum(t["duration"] for t in timeline) + card_d
    print(f"  timeline: {len(timeline)} shots + end card = {total:.1f}s")
    if not 60 <= total <= 90:
        print(f"  WARNING: film is {total:.1f}s; the brief asks for 60-90s. Adjust narration or duration_s.")

    # sound (shared by both aspect ratios)
    tag = "radio" if radio else "film"
    nkey = input_hash({"tl": [(t["narration_file"], t["duration"], t["lead"]) for t in timeline], "tail": card_d})
    narr_wav = edit / f"narration_{nkey}.wav"
    if not narr_wav.exists():
        build_narration_track(timeline, card_d, narr_wav)
    mkey = input_hash({"n": nkey, "m": music["file"], "g": sb["music"].get("music_gain_db", -6), "v": 1})
    mix_wav = edit / f"mix_{mkey}.wav"
    if not mix_wav.exists():
        print("  mixing: duck score under narration, normalise to -14 LUFS")
        build_mix(narr_wav, ROOT / music["file"], total, sb["music"].get("music_gain_db", -6), mix_wav)
    loud = measure_loudness(mix_wav)
    print(f"  loudness: {loud['integrated_lufs']} LUFS, peak {loud['true_peak_dbfs']} dBFS")

    cues = subtitle_cues(timeline)
    srt = film / f"{tag}_en.srt"
    write_srt(cues, srt)

    outputs = {}
    for aspect in (("16x9",) if radio else aspects):
        w, h = resolution(quality, aspect)
        seg_dir = outdir("edit", "segments", f"{aspect}_{quality}")
        segs = []
        for item in timeline:
            src = None if radio else shots[item["shot"]]
            segs.append(render_segment(src, item, w, h, fps, seg_dir))
            print(f"  {aspect} {item['shot']}: {item['duration']:.2f}s  {'black' if radio else src['type']}")
        card, _ = render_end_card(sb, w, h, fps, seg_dir)
        segs.append(card)
        picture = edit / f"picture_{tag}_{aspect}.mp4"
        concat(segs, picture)
        ass = edit / f"subs_{tag}_{aspect}.ass"
        write_ass(subtitle_cues(timeline, 30 if h > w else 40), w, h, ass)
        final = film / f"{tag}_{aspect}_{quality}.mp4"
        # run from edit/ so the ass filter sees a relative path (Windows drive colons break filter args)
        ffmpeg(["-i", picture.name, "-i", mix_wav.name,
                "-vf", f"ass={ass.name},fade=t=in:d=0.5", "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-shortest", str(final)], cwd=edit)
        outputs[aspect] = rel(final)
        print(f"  -> {rel(final)}  ({media_duration(final):.1f}s)")

    report = {"total_s": round(total, 2), "timeline": timeline, "loudness": loud, "outputs": outputs,
              "score": music, "subtitles": rel(srt)}
    (edit / f"timeline_{tag}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radio", action="store_true", help="narration + score + subtitles over black")
    ap.add_argument("--aspect", choices=ASPECTS, help="only one aspect ratio")
    a = ap.parse_args()
    run(a.radio, (a.aspect,) if a.aspect else ASPECTS)
