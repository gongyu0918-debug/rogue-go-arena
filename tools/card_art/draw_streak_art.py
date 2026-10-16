"""Draw medallion art for momentum, iron_wall, capture_chain in the cards-tech style.
Usage: draw_streak_art.py OUT_DIR"""
import math, os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops

OUT = sys.argv[1]
S = 1024
TEAL = (70, 230, 215)
GOLD = (255, 196, 84)
rng = random.Random(7)

def add(base, layer):
    """Additive blend (screen-like glow)."""
    r = ImageChops.add(base.convert("RGB"), layer.convert("RGB"))
    out = r.convert("RGBA"); out.putalpha(base.getchannel("A")); return out

def glow(draw_fn, color, width, blurs=(6, 22, 60), gains=(1.0, 0.9, 0.7)):
    core = Image.new("RGB", (S, S), (0, 0, 0))
    draw_fn(ImageDraw.Draw(core), color, width)
    out = core.copy()
    for b, g in zip(blurs, gains):
        h = core.filter(ImageFilter.GaussianBlur(b)).point(lambda v: min(255, int(v * g * 1.6)))
        out = ImageChops.add(out, h)
    hot = Image.new("RGB", (S, S), (0, 0, 0))
    draw_fn(ImageDraw.Draw(hot), (255, 250, 230), max(2, width // 3))
    return ImageChops.add(out, hot.filter(ImageFilter.GaussianBlur(1)))

def background(tint=(18, 70, 74)):
    im = Image.new("RGBA", (S, S), (5, 8, 11, 255))
    rad = Image.new("RGB", (S, S), (0, 0, 0))
    d = ImageDraw.Draw(rad)
    for r in range(S // 2, 0, -6):
        k = (1 - r / (S / 2)) ** 1.6
        d.ellipse((S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r), fill=tuple(int(c * k) for c in tint))
    im = add(im, rad)
    grid = Image.new("RGB", (S, S), (0, 0, 0))
    g = ImageDraw.Draw(grid)
    step = S // 10
    for i in range(1, 10):
        g.line((i * step, 0, i * step, S), fill=(14, 52, 52), width=2)
        g.line((0, i * step, S, i * step), fill=(14, 52, 52), width=2)
    im = add(im, grid)
    noise = Image.effect_noise((S, S), 18).convert("RGB").point(lambda v: max(0, v - 120) // 3)
    im = add(im, noise)
    dots = Image.new("RGB", (S, S), (0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for _ in range(70):
        x, y, r = rng.randrange(80, S - 80), rng.randrange(80, S - 80), rng.choice([2, 2, 3, 4])
        c = TEAL if rng.random() < 0.6 else GOLD
        dd.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(v * rng.uniform(0.4, 1)) for v in c))
    im = add(im, dots.filter(ImageFilter.GaussianBlur(1.5)))
    im = add(im, dots.filter(ImageFilter.GaussianBlur(8)))
    return im

def stone(im, cx, cy, r, white, rim=TEAL):
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((cx - r + 8, cy - r + 22, cx + r + 8, cy + r + 22), fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    st = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    for i in range(60, 0, -1):
        t = i / 60
        ox, oy = cx - r * 0.34 * (1 - t), cy - r * 0.38 * (1 - t)
        if white:
            v = 168 + int(84 * (1 - t) ** 0.6)
            c = (v, v, max(0, v - 8))
        else:
            v = 10 + int(95 * (1 - t) ** 2.6)
            c = (v, v + 3, v + 6)
        d.ellipse((ox - r * t, oy - r * t, ox + r * t, oy + r * t), fill=c + (255,))
    im.alpha_composite(st)
    edge = glow(lambda dr, c, w: dr.arc((cx - r, cy - r, cx + r, cy + r), 200, 300, fill=c, width=w), rim, 4, blurs=(3, 10), gains=(0.6, 0.4))
    return add(im, edge)

def vignette(im):
    v = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(v)
    for r in range(S // 2, S // 4, -4):
        a = int(200 * ((r - S / 4) / (S / 4)) ** 2.2)
        d.ellipse((S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r), outline=a, width=5)
    dark = Image.new("RGBA", (S, S), (0, 0, 0, 255)); dark.putalpha(v.filter(ImageFilter.GaussianBlur(12)))
    im.alpha_composite(dark)
    return im

def momentum():
    im = background()
    # motion streaks behind a charging line of black stones toward a white stone
    path = [(250, 770), (420, 600), (590, 430)]
    def streaks(d, c, w):
        for k, (x, y) in enumerate(path):
            for j in range(-2, 3):
                off = j * 22
                d.line([(x - 190 + off, y + 190 + off), (x - 40 + off, y + 40 + off)], fill=c, width=max(3, w - abs(j) * 4))
    im = add(im, glow(streaks, GOLD, 14))
    burst = glow(lambda d, c, w: [d.line([(735, 290), (735 + 150 * math.cos(a), 290 + 150 * math.sin(a))], fill=c, width=w) for a in [i * math.pi / 6 for i in range(12)]], GOLD, 6, blurs=(4, 18, 50))
    im = add(im, burst)
    im = stone(im, 735, 290, 92, True, rim=GOLD)
    for (x, y), r in zip(path, (78, 90, 102)):
        im = stone(im, x, y, r, False)
    return vignette(im)

def iron_wall():
    im = background(tint=(14, 64, 78))
    im = add(im, glow(lambda d, c, w: d.arc((150, 150, 874, 874), 195, 345, fill=c, width=w), TEAL, 26))
    im = add(im, glow(lambda d, c, w: d.arc((205, 205, 819, 819), 200, 340, fill=c, width=w), GOLD, 10, blurs=(4, 16, 40)))
    hexes = glow(lambda d, c, w: [d.regular_polygon((x, y, 46), 6, outline=c, width=w) for x in range(290, 760, 92) for y in (330, 410) if (x - 512) ** 2 + (y - 420) ** 2 < 300 ** 2], TEAL, 3, blurs=(4, 12), gains=(0.5, 0.4))
    im = add(im, hexes)
    im = add(im, glow(lambda d, c, w: d.line([(200, 690), (824, 690)], fill=c, width=w), GOLD, 12))
    for x in (240, 376, 512, 648, 784):
        im = stone(im, x, 690, 70, False)
    for x in (308, 444, 580, 716):
        im = stone(im, x, 572, 66, False)
    return vignette(im)

def capture_chain():
    im = background(tint=(20, 62, 70))
    # ghost white stones breaking into sparks
    for x, y, r in [(300, 300, 70), (760, 640, 58)]:
        ghost = glow(lambda d, c, w: d.ellipse((x - r, y - r, x + r, y + r), outline=c, width=w), (150, 150, 140), 5, blurs=(4, 14), gains=(0.5, 0.3))
        im = add(im, ghost)
        sp = Image.new("RGB", (S, S), (0, 0, 0))
        sd = ImageDraw.Draw(sp)
        for _ in range(26):
            a, dist = rng.uniform(0, 2 * math.pi), rng.uniform(r * 0.8, r * 1.9)
            px, py = x + dist * math.cos(a), y + dist * math.sin(a)
            sd.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(220, 220, 205))
        im = add(im, sp.filter(ImageFilter.GaussianBlur(2)))
    def links(d, c, w):
        for i in range(4):
            x, y = 330 + i * 120, 690 - i * 120
            if i % 2 == 0:
                box = (x - 105, y - 58, x + 105, y + 58)
            else:
                box = (x - 58, y - 105, x + 58, y + 105)
            d.ellipse(box, outline=c, width=w)
    chain = Image.new("RGB", (S, S), (0, 0, 0))
    chain = glow(links, (210, 150, 52), 20, blurs=(5, 18, 46), gains=(0.55, 0.45, 0.35))
    chain = chain.rotate(0)
    im = add(im, chain)
    im = stone(im, 220, 800, 86, False, rim=GOLD)
    im = stone(im, 805, 225, 86, False, rim=GOLD)
    return vignette(im)

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).ellipse((24, 24, S - 24, S - 24), fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(2))
os.makedirs(OUT, exist_ok=True)
for name, fn in (("momentum", momentum), ("iron_wall", iron_wall), ("capture_chain", capture_chain)):
    im = fn().convert("RGBA")
    im.putalpha(mask)
    small = im.resize((256, 256), Image.LANCZOS)
    small.quantize(256, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG).save(os.path.join(OUT, f"{name}.png"), optimize=True)
print("drawn")
