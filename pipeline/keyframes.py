"""Stage: keyframes. A reference image per character first, then one keyframe per shot.

Consistency comes from three things every prompt shares: the character's fixed description,
the style block, and (FLUX.2 only) the reference image itself.

Reads:  storyboard.json (style, models, characters, shots[].image_prompt/seed)
Writes: outputs/keyframes/ref_<char>_<hash>.png, outputs/keyframes/<shot>_<hash>.png, manifest.json
"""
from __future__ import annotations

import argparse
import io
import textwrap
from pathlib import Path

from common import call_logged, input_hash, load_storyboard, outdir, read_manifest, rel, select_shots, write_manifest


def reference_prompt(sb: dict, char: dict) -> str:
    return (f"character reference portrait of {char['description']}, front view, head and shoulders, "
            f"neutral calm expression, plain soft background, {sb['style']['style_block']}")


def shot_prompt(sb: dict, shot: dict) -> str:
    chars = {c["id"]: c for c in sb["characters"]}
    who = "; ".join(chars[c]["description"] for c in shot.get("characters", []))
    subject = f"{who}, {shot['image_prompt']}" if who else shot["image_prompt"]
    return f"{subject}. {sb['style']['style_block']}"


def _save_png(raw: bytes, path: Path) -> None:
    from PIL import Image

    Image.open(io.BytesIO(raw)).convert("RGB").save(path, "PNG")


def _placeholder(path: Path, label: str, prompt: str, size: int) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):  # warm vertical gradient so Ken Burns motion is visible
        t = y / size
        d.line([(0, y), (size, y)], fill=(int(70 + 120 * t), int(45 + 60 * t), int(30 + 20 * t)))
    d.ellipse([size * .35, size * .3, size * .65, size * .6], outline=(240, 220, 190), width=6)
    d.text((40, 40), f"PLACEHOLDER {label}", fill=(255, 255, 255))
    d.multiline_text((40, size - 200), "\n".join(textwrap.wrap(prompt, 90)[:6]), fill=(255, 240, 220))
    img.save(path, "PNG")


def _generate(sb: dict, *, prompt: str, seed: int, path: Path, shot: str, refs: list[Path]) -> None:
    from providers import cf_image, flux_neurons

    m = sb["models"]
    size = m.get("image_size", 1024)
    ref_bytes = [p.read_bytes() for p in refs] if m["use_reference_images"] else []
    raw = call_logged(
        stage="keyframes", provider="cloudflare", model=m["image"], shot=shot, seed=seed,
        params={"prompt": prompt, "steps": m["image_steps"], "size": size, "n_refs": len(ref_bytes),
                "send_seed": m.get("send_seed", True)},
        fn=lambda: cf_image(m["image"], prompt, seed=seed, steps=m["image_steps"], width=size, height=size,
                            reference_images=ref_bytes, send_seed=m.get("send_seed", True)),
        cost_units=lambda _r: flux_neurons(m["image"], size, size, m["image_steps"], len(ref_bytes)),
        unit_name="cf_neurons",
    )
    _save_png(raw, path)


def run(only: list[str] | None = None, placeholders: bool = False, force: bool = False,
        refs_only: bool = False) -> dict:
    sb = load_storyboard()
    out = outdir("keyframes")
    manifest = read_manifest("keyframes")
    m = sb["models"]
    size = m.get("image_size", 1024)
    tag = "_placeholder" if placeholders else ""

    # 1. character reference sheet (always before shots)
    ref_paths: dict[str, Path] = {}
    for char in sb["characters"]:
        prompt = reference_prompt(sb, char)
        h = input_hash({"model": m["image"], "steps": m["image_steps"], "size": size,
                        "prompt": prompt, "seed": char["seed"]})
        path = out / f"ref_{char['id']}_{h}{tag}.png"
        if path.exists() and not force:
            print(f"  ref {char['id']}: cached  {rel(path)}")
        elif placeholders:
            _placeholder(path, f"REF {char['id']}", prompt, size)
        else:
            print(f"  ref {char['id']}: generating ...")
            _generate(sb, prompt=prompt, seed=char["seed"], path=path, shot=f"ref_{char['id']}", refs=[])
        ref_paths[char["id"]] = path
        manifest[f"ref_{char['id']}"] = {"file": rel(path), "hash": h, "prompt": prompt}
    if refs_only:
        write_manifest("keyframes", manifest)
        return manifest

    # 2. one keyframe per shot, conditioned on the references of the characters in it
    for shot in select_shots(sb, only):
        sid = shot["id"]
        prompt = shot_prompt(sb, shot)
        refs = [ref_paths[c] for c in shot.get("characters", [])] if shot.get("use_reference", True) else []
        key = {"model": m["image"], "steps": m["image_steps"], "size": size, "prompt": prompt,
               "seed": shot["seed"], "refs": [r.name for r in refs] if m["use_reference_images"] else []}
        h = input_hash(key)
        path = out / f"{sid}_{h}{tag}.png"
        if path.exists() and not force:
            print(f"  {sid}: cached  {rel(path)}")
        elif placeholders:
            _placeholder(path, sid, prompt, size)
            print(f"  {sid}: PLACEHOLDER image (no API call)")
        else:
            print(f"  {sid}: generating ...")
            _generate(sb, prompt=prompt, seed=shot["seed"], path=path, shot=sid, refs=refs)
        manifest[sid] = {"file": rel(path), "hash": h, "prompt": prompt, "placeholder": placeholders}

    write_manifest("keyframes", manifest)
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="shot ids, e.g. s03 s07")
    ap.add_argument("--refs-only", action="store_true", help="only generate the character reference sheet")
    ap.add_argument("--placeholders", action="store_true", help="drawn stand-ins, no API calls")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(a.only, a.placeholders, a.force, a.refs_only)
