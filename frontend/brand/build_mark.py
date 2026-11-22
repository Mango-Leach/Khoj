"""Rebuilds khoj-mark.svg from khoj-logo-original.png (the 105 px logo the team supplied).

The source is small and has compression noise, so the shapes are cleaned up rather than traced as they are: the head
becomes an exact circle, the star an exact five-point star fitted to the original, and the body and light leg are traced
from smoothed masks. Colours are flat, with one gentle blue gradient like the original. Run from this folder.
"""
import math
import re
import sys

import numpy as np
import vtracer
from PIL import Image, ImageDraw, ImageFilter

S = 8
im = Image.open("khoj-logo-original.png").convert("RGB").crop((10, 0, 100, 98))
big = im.resize((im.width * S, im.height * S), Image.LANCZOS)
W, H = big.size
a = np.asarray(big).astype(float)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
ink = (255 - a.min(-1)) > 60
gold = ink & (r > 200) & (b < 160)
light = ink & ~gold & (g > 120) & (r < 150) & (b > 200)
blue = ink & ~gold & ~light


def components(mask):
    """Connected blobs of a boolean mask, biggest first, as lists of (y, x) arrays."""
    seen = np.zeros(mask.shape, bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append(np.array(pts))
    return sorted(out, key=len, reverse=True)


def mask_of(points):
    m = np.zeros((H, W), bool)
    m[points[:, 0], points[:, 1]] = True
    return m


def trace(mask, name, blur, speckle=60):
    img = Image.fromarray(np.where(mask, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(blur))
    img = img.point(lambda v: 0 if v < 128 else 255)
    img.save(f"_m_{name}.png")
    vtracer.convert_image_to_svg_py(
        f"_m_{name}.png", f"_m_{name}.svg", colormode="binary", hierarchical="stacked", mode="spline",
        filter_speckle=speckle, corner_threshold=70, length_threshold=8.0, max_iterations=10, splice_threshold=45, path_precision=1,
    )
    svg = open(f"_m_{name}.svg").read()
    paths = re.findall(r'<path d="([^"]+)" fill="(#[0-9a-fA-F]{6})" transform="([^"]+)"', svg)
    return "".join(f'<path d="{d}" transform="{t}"/>' for d, f, t in paths if f.lower() in ("#000000", "#010101", "#000001"))


def star_points(cx, cy, R, ratio, rot):
    pts = []
    for i in range(10):
        ang = math.radians(rot - 90 + i * 36)
        rad = R if i % 2 == 0 else R * ratio
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


# --- head: an exact circle from the second biggest blue blob
blobs = components(blue)
body_pts, head_pts = blobs[0], blobs[1]
hy, hx = head_pts.mean(0)
head_r = math.sqrt(len(head_pts) / math.pi)
print("head", round(hx), round(hy), round(head_r))
body_mask = mask_of(body_pts)

# --- star: grid search a regular star against the gold blob
star_blob = components(gold)[0]
gy, gx = star_blob.mean(0)
gold_mask = mask_of(star_blob)
best = (0, None)
for rot in range(-25, 26, 1):
    for ratio in (0.38, 0.42, 0.46, 0.5):
        for R in range(int(0.9 * 60), int(1.35 * 60) + 1, 4):
            im2 = Image.new("L", (W, H), 0)
            ImageDraw.Draw(im2).polygon(star_points(gx, gy, R * 1.0, ratio, rot), fill=255)
            m = np.asarray(im2) > 0
            iou = (m & gold_mask).sum() / (m | gold_mask).sum()
            if iou > best[0]:
                best = (iou, (R, ratio, rot))
print("star iou", round(best[0], 3), best[1])
R, ratio, rot = best[1]
star = " ".join(f"{x:.1f},{y:.1f}" for x, y in star_points(gx, gy, R, ratio, rot))

body_svg = trace(body_mask, "body", 4)
light_svg = trace(light, "light", 3, 40)

# crop box with a little air around the artwork
ys, xs = np.nonzero(blue | light | gold)
pad = 24
x0, y0, x1, y1 = xs.min() - pad, ys.min() - pad, xs.max() + pad, ys.max() + pad
vw, vh = x1 - x0, y1 - y0
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {vw} {vh}" width="{vw}" height="{vh}" role="img" aria-label="KHOJ">'
    f'<defs><linearGradient id="kg" gradientUnits="userSpaceOnUse" x1="{x0 + 40}" y1="{y1 - 20}" x2="{x1 - 90}" y2="{y0 + 140}">'
    '<stop offset="0" stop-color="#05278a"/><stop offset="1" stop-color="#1668dc"/></linearGradient></defs>'
    f'<g fill="url(#kg)">{body_svg}<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{head_r:.1f}" fill="#0f5ccc"/></g>'
    f'<g fill="#4a9cfb">{light_svg}</g>'
    f'<polygon points="{star}" fill="#fbb803" stroke="#fbb803" stroke-width="6" stroke-linejoin="round"/>'
    "</svg>"
)
open("khoj-mark.svg", "w").write(svg)
print("svg bytes", len(svg), "viewbox", (round(x0), round(y0), round(vw), round(vh)))
sys.exit(0)
