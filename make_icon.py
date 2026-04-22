"""
Generate a polished GoAI application icon (goai.ico / goai.png).
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFilter


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _mix(c1, c2, t: float):
    return tuple(_lerp(c1[i], c2[i], t) for i in range(4))


def _vertical_gradient(size: int, top, bottom) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        color = _mix(top, bottom, y / max(1, size - 1))
        for x in range(size):
            px[x, y] = color
    return img


def _draw_gloss(draw: ImageDraw.ImageDraw, box, strength: int):
    left, top, right, bottom = box
    for i in range(strength):
        if right - i <= left + i or bottom - i <= top + i:
            break
        alpha = max(0, 70 - i * 5)
        draw.arc(
            [left + i, top + i, right - i, bottom - i],
            start=210,
            end=330,
            fill=(255, 255, 255, alpha),
            width=1,
        )


def _draw_stone(base: Image.Image, cx: int, cy: int, radius: int, kind: str):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse(
        [cx - radius + 8, cy - radius + 10, cx + radius + 8, cy + radius + 10],
        fill=(0, 0, 0, 72),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius // 5))
    base.alpha_composite(shadow)

    stone = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(stone)
    if kind == "black":
        outer_top = (70, 73, 83, 255)
        outer_bottom = (18, 20, 25, 255)
        rim = (8, 10, 14, 255)
        gloss = (210, 225, 255, 120)
    else:
        outer_top = (255, 255, 255, 255)
        outer_bottom = (206, 212, 222, 255)
        rim = (150, 158, 170, 255)
        gloss = (255, 255, 255, 165)

    for i in range(radius * 2):
        t = i / max(1, radius * 2 - 1)
        color = _mix(outer_top, outer_bottom, t)
        y = cy - radius + i
        width = int((radius**2 - (y - cy) ** 2) ** 0.5) if abs(y - cy) <= radius else 0
        if width > 0:
            draw.line([cx - width, y, cx + width, y], fill=color, width=1)

    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=rim, width=max(2, radius // 10))
    draw.ellipse([cx - radius // 2, cy - radius // 2, cx - radius // 8, cy - radius // 8], fill=gloss)
    draw.ellipse([cx + radius // 8, cy + radius // 10, cx + radius // 2, cy + radius // 3], fill=(255, 255, 255, 22))
    base.alpha_composite(stone)


def make_go_icon(size=256):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    board = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(board)

    outer_margin = max(2, size // 26)
    inner_margin = max(6, size // 9)
    outer = [outer_margin, outer_margin, size - outer_margin, size - outer_margin]
    inner = [inner_margin, inner_margin, size - inner_margin, size - inner_margin]
    board_grad = _vertical_gradient(size, (217, 161, 68, 255), (145, 91, 22, 255))
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle(outer, radius=size // 8, fill=255)
    board.paste(board_grad, (0, 0), mask)

    draw.rounded_rectangle(outer, radius=size // 8, outline=(92, 50, 16, 255), width=max(4, size // 48))
    draw.rounded_rectangle(inner, radius=size // 10, outline=(122, 72, 20, 190), width=max(2, size // 96))
    _draw_gloss(draw, outer, max(8, size // 28))

    grid_margin = max(8, size // 6)
    grid_left = grid_margin
    grid_top = grid_margin
    grid_right = size - grid_margin
    grid_bottom = size - grid_margin
    grid_n = 9
    step = (grid_right - grid_left) / (grid_n - 1)
    line_color = (92, 54, 18, 215)
    line_width = max(2, size // 96)

    for i in range(grid_n):
        gx = int(grid_left + i * step)
        gy = int(grid_top + i * step)
        draw.line([(gx, grid_top), (gx, grid_bottom)], fill=line_color, width=line_width)
        draw.line([(grid_left, gy), (grid_right, gy)], fill=line_color, width=line_width)

    star_points = [(2, 2), (4, 2), (6, 2), (2, 4), (4, 4), (6, 4), (2, 6), (4, 6), (6, 6)]
    star_r = max(3, size // 42)
    for sx, sy in star_points:
        x = int(grid_left + sx * step)
        y = int(grid_top + sy * step)
        draw.ellipse([x - star_r, y - star_r, x + star_r, y + star_r], fill=(70, 39, 12, 235))

    # Subtle AI motif: cool halo and circuit-like nodes behind the center.
    halo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(halo)
    center = int(grid_left + 4 * step)
    halo_radius = max(10, size // 5)
    halo_color = (77, 197, 208, 72)
    hdraw.ellipse(
        [center - halo_radius, center - halo_radius, center + halo_radius, center + halo_radius],
        outline=halo_color,
        width=max(2, size // 40),
    )
    ai_nodes = [
        (-halo_radius - size // 80, -size // 32),
        (-size // 12, halo_radius - size // 48),
        (size // 14, -halo_radius + size // 48),
        (halo_radius + size // 40, size // 20),
    ]
    for dx, dy in ai_nodes:
        x = center + dx
        y = center + dy
        hdraw.line([center, center, x, y], fill=(68, 185, 196, 88), width=max(1, size // 64))
        node_r = max(2, size // 42)
        hdraw.ellipse([x - node_r, y - node_r, x + node_r, y + node_r], fill=(119, 235, 245, 130))
    halo = halo.filter(ImageFilter.GaussianBlur(2))
    canvas.alpha_composite(board)
    canvas.alpha_composite(halo)

    stone_radius = int(step * 0.46)
    black_positions = [(2, 1), (6, 2), (4, 4), (3, 6)]
    white_positions = [(5, 2), (6, 5), (2, 4), (5, 6)]
    for gx, gy in black_positions:
        _draw_stone(canvas, int(grid_left + gx * step), int(grid_top + gy * step), stone_radius, "black")
    for gx, gy in white_positions:
        _draw_stone(canvas, int(grid_left + gx * step), int(grid_top + gy * step), stone_radius, "white")

    # Highlight one dramatic center move.
    _draw_stone(canvas, int(grid_left + 4 * step), int(grid_top + 2 * step), stone_radius + 2, "black")

    # Soft vignette for depth.
    vignette = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for i in range(size // 8):
        alpha = int(110 * (i / max(1, size // 8 - 1)) ** 2)
        vdraw.rounded_rectangle(
            [i, i, size - 1 - i, size - 1 - i],
            radius=max(size // 8 - i // 2, 4),
            outline=(20, 10, 4, alpha),
            width=2,
        )
    canvas.alpha_composite(vignette)
    return canvas


def main():
    sizes = [256, 128, 64, 48, 32, 16]
    images = [make_go_icon(s) for s in sizes]

    root = os.path.dirname(os.path.abspath(__file__))
    ico_out = os.path.join(root, "goai.ico")
    png_out = os.path.join(root, "goai.png")

    images[0].save(
        ico_out,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    images[0].save(png_out, format="PNG")
    print(f"Icon saved: {ico_out}")
    print(f"PNG saved:  {png_out}")


if __name__ == "__main__":
    main()
