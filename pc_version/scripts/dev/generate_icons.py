import math
import os
from PIL import Image, ImageDraw, ImageFilter

def create_subnova_icon(size=512, is_round=False):
    # High-res base canvas with supersampling (4x)
    base_size = size * 4
    img = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = base_size / 2
    radius = (base_size * 0.92) / 2 if is_round else base_size * 0.88 / 2

    # Background gradient
    # Deep midnight slate to obsidian
    c_top = (11, 15, 25, 255)       # #0B0F19
    c_bottom = (5, 8, 15, 255)      # #05080F
    c_glow = (0, 229, 255, 60)      # Neon cyan ambient glow

    # Draw rounded rect or circle background
    mask = Image.new("L", (base_size, base_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    if is_round:
        mask_draw.ellipse(
            (center - radius, center - radius, center + radius, center + radius),
            fill=255
        )
    else:
        corner_r = int(base_size * 0.22)
        mask_draw.rounded_rectangle(
            (center - radius, center - radius, center + radius, center + radius),
            radius=corner_r,
            fill=255
        )

    # Gradient fill
    for y in range(base_size):
        t = y / base_size
        r = int(c_top[0] * (1 - t) + c_bottom[0] * t)
        g = int(c_top[1] * (1 - t) + c_bottom[1] * t)
        b = int(c_top[2] * (1 - t) + c_bottom[2] * t)
        draw.line([(0, y), (base_size, y)], fill=(r, g, b, 255))

    # Glow layer
    glow_canvas = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_canvas)
    glow_r = int(base_size * 0.40)
    glow_draw.ellipse(
        (center - glow_r, center - glow_r * 0.8, center + glow_r, center + glow_r * 1.2),
        fill=(0, 229, 255, 75)
    )
    glow_draw.ellipse(
        (center - glow_r * 0.5, center - glow_r * 0.6, center + glow_r * 0.5, center + glow_r * 0.4),
        fill=(124, 77, 255, 60)
    )
    glow_canvas = glow_canvas.filter(ImageFilter.GaussianBlur(int(base_size * 0.08)))
    img = Image.alpha_composite(img, glow_canvas)

    # Composite with background mask
    bg_final = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    bg_final.paste(img, (0, 0), mask)
    draw = ImageDraw.Draw(bg_final)

    # Border stroke around the icon
    border_color = (0, 229, 255, 140)
    border_w = int(base_size * 0.015)
    if is_round:
        draw.ellipse(
            (center - radius, center - radius, center + radius, center + radius),
            outline=border_color, width=border_w
        )
    else:
        corner_r = int(base_size * 0.22)
        draw.rounded_rectangle(
            (center - radius, center - radius, center + radius, center + radius),
            radius=corner_r,
            outline=border_color, width=border_w
        )

    # Foreground Elements:
    # 1. Cinema / Subtitle frame card
    fg_canvas = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    fg_draw = ImageDraw.Draw(fg_canvas)

    card_w = int(base_size * 0.64)
    card_h = int(base_size * 0.46)
    card_x1 = int(center - card_w / 2)
    card_y1 = int(center - card_h / 2)
    card_x2 = int(center + card_w / 2)
    card_y2 = int(center + card_h / 2)
    card_r = int(base_size * 0.08)

    # Semi-transparent dark card background
    fg_draw.rounded_rectangle(
        (card_x1, card_y1, card_x2, card_y2),
        radius=card_r,
        fill=(16, 23, 38, 220),
        outline=(0, 229, 255, 230),
        width=int(base_size * 0.02)
    )

    # 2. Glowing "S" and Nova Sparkle in center
    # Draw stylized S curve
    s_points_top = [
        (center + int(base_size * 0.12), center - int(base_size * 0.12)),
        (center - int(base_size * 0.10), center - int(base_size * 0.12)),
        (center - int(base_size * 0.12), center - int(base_size * 0.02)),
        (center + int(base_size * 0.12), center + int(base_size * 0.02)),
        (center + int(base_size * 0.10), center + int(base_size * 0.12)),
        (center - int(base_size * 0.12), center + int(base_size * 0.12)),
    ]
    
    # Draw Subtitle Dialogue Waves [ ——  —— ]
    line_y1 = center + int(base_size * 0.14)
    line_y2 = center - int(base_size * 0.02)
    
    # Wave 1 (Cyan)
    fg_draw.rounded_rectangle(
        (center - int(base_size * 0.22), line_y1, center - int(base_size * 0.05), line_y1 + int(base_size * 0.035)),
        radius=int(base_size * 0.015),
        fill=(0, 229, 255, 255)
    )
    # Wave 2 (Green)
    fg_draw.rounded_rectangle(
        (center + int(base_size * 0.02), line_y1, center + int(base_size * 0.22), line_y1 + int(base_size * 0.035)),
        radius=int(base_size * 0.015),
        fill=(0, 230, 118, 255)
    )

    # Center Nova Star ✨
    def draw_star(cx, cy, r_outer, r_inner, color):
        points = []
        for i in range(8):
            angle = i * (math.pi / 4)
            r = r_outer if i % 2 == 0 else r_inner
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        fg_draw.polygon(points, fill=color)

    star_cx = center
    star_cy = center - int(base_size * 0.05)
    # Golden outer glow
    draw_star(star_cx, star_cy, int(base_size * 0.14), int(base_size * 0.04), (255, 215, 0, 255))
    # Core bright white/cyan star
    draw_star(star_cx, star_cy, int(base_size * 0.10), int(base_size * 0.025), (255, 255, 255, 255))

    # Corner brackets for cinematic framing
    cb_len = int(base_size * 0.07)
    cb_w = int(base_size * 0.018)
    cb_color = (0, 229, 255, 220)
    
    # Top-Left Bracket
    fg_draw.line([(card_x1 + 10, card_y1 + cb_len), (card_x1 + 10, card_y1 + 10), (card_x1 + cb_len, card_y1 + 10)], fill=cb_color, width=cb_w)
    # Bottom-Right Bracket
    fg_draw.line([(card_x2 - 10, card_y2 - cb_len), (card_x2 - 10, card_y2 - 10), (card_x2 - cb_len, card_y2 - 10)], fill=cb_color, width=cb_w)

    final_img = Image.alpha_composite(bg_final, fg_canvas)
    # Resize down with Lanczos for anti-aliasing
    return final_img.resize((size, size), Image.Resampling.LANCZOS)

if __name__ == "__main__":
    res_dir = r"android\app\src\main\res"
    densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192
    }

    for folder, dim in densities.items():
        target_dir = os.path.join(res_dir, folder)
        os.makedirs(target_dir, exist_ok=True)
        
        # Square / squircle icon
        img_square = create_subnova_icon(dim, is_round=False)
        img_square.save(os.path.join(target_dir, "ic_launcher.png"), "PNG")
        
        # Round icon
        img_round = create_subnova_icon(dim, is_round=True)
        img_round.save(os.path.join(target_dir, "ic_launcher_round.png"), "PNG")

        # Also remove old .webp icons if present to ensure .png takes priority
        for old_file in ["ic_launcher.webp", "ic_launcher_round.webp"]:
            p = os.path.join(target_dir, old_file)
            if os.path.exists(p):
                os.remove(p)

    # Also save 512x512 master icon
    master = create_subnova_icon(512, is_round=False)
    master.save(os.path.join(res_dir, "subnova_logo_512.png"), "PNG")
    print("All SubNova icons generated successfully!")
