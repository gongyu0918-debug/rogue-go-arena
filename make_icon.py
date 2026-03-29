"""
Generate GoAI application icon (goai.ico)
"""
from PIL import Image, ImageDraw, ImageFont
import math, os

def make_go_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded square background (wooden board)
    r = size // 8
    board_color = (194, 140, 40, 255)
    board_dark  = (165, 108, 20, 255)
    # Gradient simulation: draw multiple rectangles
    for i in range(size // 2):
        blend = i / (size // 2)
        c = tuple(int(board_color[j] + (board_dark[j] - board_color[j]) * blend) for j in range(3)) + (255,)
        draw.rounded_rectangle([i, i, size-1-i, size-1-i], radius=max(r-i//4, 4), fill=c)

    # Board border
    pad = size // 12
    draw.rounded_rectangle([pad//2, pad//2, size-pad//2-1, size-pad//2-1],
                            radius=r, outline=(90, 50, 15, 255), width=max(2, size//64))

    # Grid (7x7 for visibility)
    grid = 7
    x0 = pad + size//18
    y0 = pad + size//18
    x1 = size - pad - size//18
    y1 = size - pad - size//18
    step_x = (x1 - x0) / (grid - 1)
    step_y = (y1 - y0) / (grid - 1)
    lw = max(1, size // 128)

    for i in range(grid):
        gx = int(x0 + i * step_x)
        gy = int(y0 + i * step_y)
        draw.line([(gx, int(y0)), (gx, int(y1))], fill=(90, 48, 14, 200), width=lw)
        draw.line([(int(x0), gy), (int(x1), gy)], fill=(90, 48, 14, 200), width=lw)

    # Star points (3x3 on 7x7)
    for si, sj in [(1,1),(3,1),(5,1),(1,3),(3,3),(5,3),(1,5),(3,5),(5,5)]:
        sx = int(x0 + si * step_x)
        sy = int(y0 + sj * step_y)
        sr = max(2, size // 52)
        draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(80, 40, 10, 230))

    # Stones
    sr = int(step_x * 0.46)

    def stone_black(cx, cy):
        # Drop shadow
        for dx, dy in [(2,2),(1,2),(2,1)]:
            draw.ellipse([cx-sr+dx, cy-sr+dy, cx+sr+dx, cy+sr+dy],
                         fill=(0,0,0,60))
        # Stone body
        draw.ellipse([cx-sr, cy-sr, cx+sr, cy+sr], fill=(18, 18, 18, 255))
        # Highlight
        hw = max(1, sr//3)
        draw.ellipse([cx-sr+hw, cy-sr+hw, cx-sr//2, cy-sr//2],
                     fill=(100, 100, 100, 180))

    def stone_white(cx, cy):
        for dx, dy in [(2,2),(1,2),(2,1)]:
            draw.ellipse([cx-sr+dx, cy-sr+dy, cx+sr+dx, cy+sr+dy],
                         fill=(0,0,0,50))
        draw.ellipse([cx-sr, cy-sr, cx+sr, cy+sr], fill=(238, 238, 238, 255))
        draw.ellipse([cx-sr, cy-sr, cx+sr, cy+sr], outline=(160,160,160,200), width=max(1, sr//6))
        hw = max(1, sr//3)
        draw.ellipse([cx-sr+hw, cy-sr+hw, cx-sr//3, cy-sr//3],
                     fill=(255, 255, 255, 200))

    # Classic opening pattern
    positions_b = [(1,1),(3,5),(5,1),(1,5),(3,3)]
    positions_w = [(5,5),(1,3),(5,3),(3,1),(4,2)]

    for (gi, gj) in positions_b:
        stone_black(int(x0 + gi * step_x), int(y0 + gj * step_y))
    for (gi, gj) in positions_w:
        stone_white(int(x0 + gi * step_x), int(y0 + gj * step_y))

    return img


def main():
    sizes = [256, 128, 64, 48, 32, 16]
    images = [make_go_icon(s) for s in sizes]

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goai.ico")
    images[0].save(out, format="ICO", sizes=[(s, s) for s in sizes],
                   append_images=images[1:])
    print(f"Icon saved: {out}")

    # Also save a PNG for reference
    png_out = out.replace(".ico", ".png")
    images[0].save(png_out, format="PNG")
    print(f"PNG saved:  {png_out}")


if __name__ == "__main__":
    main()
