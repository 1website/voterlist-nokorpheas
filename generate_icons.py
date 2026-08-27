import os
import math
from PIL import Image, ImageDraw, ImageFont

def create_app_icons():
    output_dir = os.path.join(os.path.dirname(__file__), 'app', 'static', 'icons')
    os.makedirs(output_dir, exist_ok=True)

    # Master canvas size (4x supersampling for ultra crispness)
    SIZE = 2048
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background: Rounded rectangle with deep royal blue gradient
    radius = int(SIZE * 0.22)
    # Background rectangle
    bg_color = (15, 43, 92, 255) # #0f2b5c
    draw.rounded_rectangle([0, 0, SIZE, SIZE], radius=radius, fill=bg_color)

    # Inner subtle glow/gradient layer
    for r in range(int(SIZE * 0.45), int(SIZE * 0.1), -10):
        alpha = int(25 * (1 - r / (SIZE * 0.45)))
        center_x, center_y = SIZE // 2, int(SIZE * 0.45)
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], 
                     fill=(30, 75, 150, alpha))

    # Outer Gold Ring
    ring_margin = int(SIZE * 0.08)
    ring_thick = int(SIZE * 0.02)
    draw.ellipse([ring_margin, ring_margin, SIZE - ring_margin, SIZE - ring_margin],
                 outline=(212, 175, 55, 255), width=ring_thick)

    # Inner Gold Ring
    inner_margin = int(SIZE * 0.12)
    draw.ellipse([inner_margin, inner_margin, SIZE - inner_margin, SIZE - inner_margin],
                 outline=(245, 200, 80, 200), width=int(ring_thick * 0.4))

    # Decorative dots on the ring
    dot_radius = int(SIZE * 0.012)
    center = SIZE / 2
    r_dots = (ring_margin + inner_margin) / 2
    for i in range(24):
        angle = i * (2 * math.pi / 24)
        dx = center + r_dots * math.cos(angle)
        dy = center + r_dots * math.sin(angle)
        draw.ellipse([dx - dot_radius, dy - dot_radius, dx + dot_radius, dy + dot_radius],
                     fill=(250, 215, 100, 255))

    # Draw Central Emblem: Khmer Temple Spire & Ballot Box
    # 1. Temple Spire (Top Part)
    spire_top = int(SIZE * 0.22)
    spire_center_x = SIZE // 2
    
    # Gold color palette
    gold_light = (255, 225, 120, 255)
    gold_mid = (212, 175, 55, 255)
    gold_dark = (160, 120, 30, 255)

    # Spire needle
    draw.polygon([
        (spire_center_x, spire_top),
        (spire_center_x - 30, spire_top + 120),
        (spire_center_x + 30, spire_top + 120)
    ], fill=gold_light)

    # Multi-tier temple tiers
    tiers = [
        (120, 200, 70),
        (190, 320, 80),
        (300, 480, 90),
        (450, 680, 100)
    ]
    
    curr_y = spire_top + 110
    for w_top, w_bot, h in tiers:
        # Tier polygon
        draw.polygon([
            (spire_center_x - w_top // 2, curr_y),
            (spire_center_x + w_top // 2, curr_y),
            (spire_center_x + w_bot // 2, curr_y + h),
            (spire_center_x - w_bot // 2, curr_y + h)
        ], fill=gold_mid)
        # Tier highlight
        draw.line([
            (spire_center_x - w_bot // 2, curr_y + h),
            (spire_center_x + w_bot // 2, curr_y + h)
        ], fill=gold_light, width=12)
        curr_y += h + 15

    # 2. Central Ballot Box / Modern Card Base
    box_w = int(SIZE * 0.52)
    box_h = int(SIZE * 0.32)
    box_x0 = (SIZE - box_w) // 2
    box_y0 = int(SIZE * 0.52)
    box_x1 = box_x0 + box_w
    box_y1 = box_y0 + box_h

    # Shadow
    draw.rounded_rectangle([box_x0 + 10, box_y0 + 20, box_x1 + 10, box_y1 + 20], 
                           radius=40, fill=(5, 15, 35, 180))
    # Box body (White/Cream clean plate)
    draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=40, 
                           fill=(248, 250, 252, 255), outline=(212, 175, 55, 255), width=16)

    # Ballot Slot on Top of Box
    slot_w = int(box_w * 0.45)
    slot_h = 24
    slot_x0 = (SIZE - slot_w) // 2
    slot_y0 = box_y0 + 40
    draw.rounded_rectangle([slot_x0, slot_y0, slot_x0 + slot_w, slot_y0 + slot_h], 
                           radius=12, fill=(30, 41, 59, 255))

    # Vote Checkmark Badge (Emerald Green Circle with Crisp White Checkmark)
    check_r = int(SIZE * 0.11)
    check_cx = SIZE // 2
    check_cy = box_y0 + int(box_h * 0.62)
    
    # Badge border & shadow
    draw.ellipse([check_cx - check_r - 8, check_cy - check_r - 8, 
                  check_cx + check_r + 8, check_cy + check_r + 8], fill=(212, 175, 55, 255))
    draw.ellipse([check_cx - check_r, check_cy - check_r, 
                  check_cx + check_r, check_cy + check_r], fill=(16, 185, 129, 255)) # Emerald-500

    # White Checkmark
    chk_thick = 36
    # Point 1 (left), Point 2 (bottom corner), Point 3 (top right)
    p1 = (check_cx - int(check_r * 0.48), check_cy - int(check_r * 0.05))
    p2 = (check_cx - int(check_r * 0.12), check_cy + int(check_r * 0.38))
    p3 = (check_cx + int(check_r * 0.50), check_cy - int(check_r * 0.40))
    
    draw.line([p1, p2], fill=(255, 255, 255, 255), width=chk_thick, joint="curve")
    draw.line([p2, p3], fill=(255, 255, 255, 255), width=chk_thick, joint="curve")
    # Rounded joints at tips
    r_cap = chk_thick // 2
    draw.ellipse([p1[0]-r_cap, p1[1]-r_cap, p1[0]+r_cap, p1[1]+r_cap], fill=(255, 255, 255, 255))
    draw.ellipse([p2[0]-r_cap, p2[1]-r_cap, p2[0]+r_cap, p2[1]+r_cap], fill=(255, 255, 255, 255))
    draw.ellipse([p3[0]-r_cap, p3[1]-r_cap, p3[0]+r_cap, p3[1]+r_cap], fill=(255, 255, 255, 255))

    # Bottom Text/Banner: "VOTER LIST" or "នគរភាស"
    # Ribbon at bottom
    ribbon_w = int(SIZE * 0.65)
    ribbon_h = int(SIZE * 0.09)
    ribbon_x0 = (SIZE - ribbon_w) // 2
    ribbon_y0 = int(SIZE * 0.86)
    draw.rounded_rectangle([ribbon_x0, ribbon_y0, ribbon_x0 + ribbon_w, ribbon_y0 + ribbon_h],
                           radius=28, fill=(212, 175, 55, 255), outline=(255, 235, 160, 255), width=8)

    # Stars / Embellishments on ribbon
    star_y = ribbon_y0 + ribbon_h // 2
    for offset in [-int(ribbon_w * 0.40), int(ribbon_w * 0.40)]:
        sx = SIZE // 2 + offset
        draw.ellipse([sx - 16, star_y - 16, sx + 16, star_y + 16], fill=(15, 43, 92, 255))

    # Save multiple sizes
    sizes = {
        'icon-512x512.png': (512, 512),
        'icon-192x192.png': (192, 192),
        'apple-touch-icon.png': (180, 180),
        'favicon-32x32.png': (32, 32),
        'favicon-16x16.png': (16, 16),
    }

    for filename, (w, h) in sizes.items():
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        out_path = os.path.join(output_dir, filename)
        resized.save(out_path, format="PNG", optimize=True)
        print(f"Generated: {filename} ({w}x{h})")

    # Generate Maskable Icon (full bleed background, no rounded outer corners so OS can crop safely)
    maskable_img = Image.new("RGBA", (SIZE, SIZE), bg_color)
    # Scale down master emblem by 80% to fit within safe maskable circle
    emblem_scale = 0.82
    scaled_w = int(SIZE * emblem_scale)
    scaled_h = int(SIZE * emblem_scale)
    scaled_emblem = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    offset_x = (SIZE - scaled_w) // 2
    offset_y = (SIZE - scaled_h) // 2
    maskable_img.paste(scaled_emblem, (offset_x, offset_y), scaled_emblem)
    
    maskable_512 = maskable_img.resize((512, 512), Image.Resampling.LANCZOS)
    maskable_path = os.path.join(output_dir, 'icon-maskable-512x512.png')
    maskable_512.save(maskable_path, format="PNG", optimize=True)
    print("Generated: icon-maskable-512x512.png (512x512)")

    # Generate favicon.ico (containing 16x16, 32x32, 48x48)
    ico_img = img.resize((48, 48), Image.Resampling.LANCZOS)
    ico_path = os.path.join(output_dir, 'favicon.ico')
    ico_img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    # Also save to static root for standard browser fallback
    root_ico_path = os.path.join(os.path.dirname(__file__), 'app', 'static', 'favicon.ico')
    ico_img.save(root_ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print("Generated: favicon.ico")

if __name__ == '__main__':
    create_app_icons()
