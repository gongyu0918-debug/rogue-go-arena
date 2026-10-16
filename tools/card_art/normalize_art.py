"""Crop each card art to its central motif and mask it into a uniform circle.

Usage: normalize_art.py SRC_DIR OUT_DIR SHEET_PNG [id=crop_factor ...]
The default crop is 0.78 of the art's content box; SHEET_PNG is a contact
sheet for checking the result by eye.
"""
import sys, glob, os
from PIL import Image, ImageDraw, ImageFilter

SRC, OUT, SHEET = sys.argv[1:4]
OVERRIDES = {k: float(v) for k, v in (a.split("=") for a in sys.argv[4:])}
SIZE = 256
os.makedirs(OUT, exist_ok=True)

def content_bbox(im):
    px = im.load(); w, h = im.size
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if a > 40 and (r + g + b) > 60:
                xs.append(x); ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)

mask = Image.new("L", (SIZE * 4, SIZE * 4), 0)
ImageDraw.Draw(mask).ellipse((6, 6, SIZE * 4 - 6, SIZE * 4 - 6), fill=255)
mask = mask.resize((SIZE, SIZE), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))

files = sorted(glob.glob(os.path.join(SRC, "*.png")))
for f in files:
    cid = os.path.splitext(os.path.basename(f))[0]
    im = Image.open(f).convert("RGBA")
    x0, y0, x1, y1 = content_bbox(im)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = OVERRIDES.get(cid, 0.78) * min(x1 - x0, y1 - y0)
    crop = im.crop((int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2)))
    bg = Image.new("RGBA", crop.size, (8, 12, 16, 255))
    bg.alpha_composite(crop)
    out = bg.resize((SIZE, SIZE), Image.LANCZOS)
    out.putalpha(mask)
    out.quantize(256, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG).save(os.path.join(OUT, f"{cid}.png"), optimize=True)

outs = sorted(glob.glob(os.path.join(OUT, "*.png")))
W, cols = 112, 10
rows = (len(outs) + cols - 1) // cols
sheet = Image.new("RGBA", (cols * W, rows * (W + 14)), (60, 50, 40, 255))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(outs):
    x, y = (i % cols) * W, (i // cols) * (W + 14)
    sheet.alpha_composite(Image.open(f).convert("RGBA").resize((W - 8, W - 8), Image.LANCZOS), (x + 4, y + 4))
    d.text((x + 4, y + W - 4), os.path.basename(f)[:-4][:16], fill=(230, 220, 200, 255))
sheet.save(SHEET)
print(len(outs), "normalized")
