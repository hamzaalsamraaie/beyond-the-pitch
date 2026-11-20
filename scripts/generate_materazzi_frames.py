"""
Phase B graphics — Materazzi concept.

Generates 9 storyboard frames (1080×1920 PNG) + a 3×3 contact sheet.
All frames are original work except where CC-BY photos are composited.
Run from the project root with the venv active.
"""

from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

ROOT    = Path(__file__).resolve().parents[1]
OUT     = ROOT / "output" / "phase_b_materazzi"
PHOTOS  = OUT / "assets" / "photos"
GFXDIR  = OUT / "assets" / "graphics"
GFXDIR.mkdir(parents=True, exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY    = (13,  27,  42)
NAVY2   = (8,   18,  30)
GOLD    = (201, 168, 76)
GOLD2   = (230, 195, 100)
WHITE   = (255, 255, 255)
BLACK   = (0,   0,   0)
RED     = (210, 45,  45)
GREY    = (120, 130, 140)
LIGHT   = (200, 210, 220)
FR_BLUE = (0,   85,  164)
FR_RED  = (239, 65,  53)
IT_GRN  = (0,   140, 69)
IT_RED  = (206, 43,  55)
PITCH   = (28,  95,  52)
LINE    = (210, 235, 210)

W, H = 1080, 1920

# ── Fonts ─────────────────────────────────────────────────────────────────────
_DIN  = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
_ARBL = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_AR   = "/System/Library/Fonts/Supplemental/Arial.ttf"

def fnt(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

# ── Drawing helpers ───────────────────────────────────────────────────────────

def new_frame(bg=NAVY) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def center_x(draw: ImageDraw.ImageDraw, text: str, f) -> int:
    bb = draw.textbbox((0, 0), text, font=f)
    return (W - (bb[2] - bb[0])) // 2


def draw_text_centered(draw, y, text, f, fill, shadow_col=(0, 0, 0)):
    x = center_x(draw, text, f)
    draw.text((x + 2, y + 2), text, font=f, fill=shadow_col)
    draw.text((x, y), text, font=f, fill=fill)
    bb = draw.textbbox((0, 0), text, font=f)
    return bb[3] - bb[1]


def gold_rule(draw, y, margin=100):
    draw.rectangle([margin, y, W - margin, y + 2], fill=GOLD)


def corner_badge(draw, label, minute):
    """'108'' badge, top-right."""
    bw, bh = 200, 70
    draw.rectangle([W - bw - 20, 30, W - 20, 30 + bh], fill=GOLD)
    f = fnt(_DIN, 46)
    bb = draw.textbbox((0, 0), minute, font=f)
    tw = bb[2] - bb[0]
    draw.text((W - 20 - tw - 15, 30 + (bh - (bb[3] - bb[1])) // 2), minute,
              font=f, fill=NAVY)


def watermark(draw):
    f = fnt(_AR, 28)
    draw.text((30, H - 50), "BEYOND THE PITCH", font=f, fill=(GOLD[0], GOLD[1], GOLD[2], 180))


def photo_fill(path: Path) -> Image.Image:
    """Center-crop a photo to 1080×1920."""
    if not path.exists():
        img, d = new_frame((40, 40, 55))
        f = fnt(_AR, 36)
        draw_text_centered(d, H // 2 - 20, f"[PHOTO: {path.name}]", f, GOLD)
        return img
    img = Image.open(path).convert("RGB")
    iw, ih = img.size
    target_r = W / H
    img_r    = iw / ih
    if img_r > target_r:
        new_w = int(ih * target_r)
        x0    = (iw - new_w) // 2
        img   = img.crop((x0, 0, x0 + new_w, ih))
    else:
        new_h = int(iw / target_r)
        y0    = (ih - new_h) // 2
        img   = img.crop((0, y0, iw, y0 + new_h))
    return img.resize((W, H), Image.LANCZOS)


def add_overlay(base: Image.Image, color=NAVY, opacity=0.55) -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (*color, int(255 * opacity)))
    out     = base.convert("RGBA")
    Image.alpha_composite(out, overlay)
    return out.convert("RGB")


def add_bottom_gradient(base: Image.Image, height=600, opacity=0.90) -> Image.Image:
    grad    = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d       = ImageDraw.Draw(grad)
    for i in range(height):
        alpha = int(255 * opacity * (i / height))
        d.rectangle([0, H - height + i, W, H - height + i + 1],
                    fill=(*NAVY2, alpha))
    result = base.convert("RGBA")
    result.paste(grad, (0, 0), grad)
    return result.convert("RGB")


# ── SHOT 1 — Hook Line 1 ──────────────────────────────────────────────────────
# Materazzi portrait, bottom identity bar, name label
def shot_01() -> Image.Image:
    base = photo_fill(PHOTOS / "materazzi_cc_by_2.0.jpg")
    # Enhance the small photo to reduce softness appearance
    base = ImageEnhance.Sharpness(base).enhance(1.4)
    base = add_bottom_gradient(base, height=700, opacity=0.95)

    img = base.copy()
    d   = ImageDraw.Draw(img)

    # Bottom identity bar
    bar_y = H - 220
    d.rectangle([0, bar_y, W, H], fill=NAVY2)
    gold_rule(d, bar_y, margin=0)

    f_name  = fnt(_DIN, 80)
    f_title = fnt(_AR, 36)

    draw_text_centered(d, bar_y + 28, "MARCO MATERAZZI", f_name, GOLD)
    draw_text_centered(d, bar_y + 118, "Italy · Inter Milan · 2006 World Cup Winner", f_title, LIGHT)

    # Minimal Beyond The Pitch badge top-right
    f_badge = fnt(_AR, 26)
    d.text((W - 310, 36), "BEYOND THE PITCH", font=f_badge, fill=GOLD)

    return img


# ── SHOT 2 — Hook Line 2 (subversion) ────────────────────────────────────────
# Same photo, darker overlay, gold central statement text
def shot_02() -> Image.Image:
    base = photo_fill(PHOTOS / "materazzi_cc_by_2.0.jpg")
    base = ImageEnhance.Sharpness(base).enhance(1.4)
    base = add_overlay(base, NAVY2, opacity=0.68)

    img = base.copy()
    d   = ImageDraw.Draw(img)

    f_top  = fnt(_AR,  40)
    f_main = fnt(_DIN, 88)
    f_sub  = fnt(_DIN, 72)

    # Setup label
    draw_text_centered(d, 160, "EVERYONE KNOWS THE HEADBUTT.", f_top, LIGHT)
    gold_rule(d, 240)

    # Central reveal text
    h1 = draw_text_centered(d, H // 2 - 100, "NOBODY REMEMBERS", f_main, WHITE)
    draw_text_centered(d, H // 2 - 100 + h1 + 16, "WHAT HE ACTUALLY DID.", f_sub, GOLD)

    watermark(d)
    return img


# ── SHOT 3 — Penalty Diagram ──────────────────────────────────────────────────
def shot_03() -> Image.Image:
    img, d = new_frame(NAVY)

    f_hdr = fnt(_DIN, 72)
    f_lbl = fnt(_DIN, 56)
    f_p   = fnt(_AR,  28)

    draw_text_centered(d, 70, "7'  —  THE FOUL", f_hdr, GOLD)
    gold_rule(d, 158)

    # ── Pitch: fills most of the frame ───────────────────────────────────────
    PX, PY, PW, PH = 90, 190, 900, 980
    d.rectangle([PX, PY, PX + PW, PY + PH], fill=PITCH)
    d.rectangle([PX, PY, PX + PW, PY + PH], outline=LINE, width=3)

    # Goal line and goal mouth at bottom of diagram
    goal_y = PY + PH
    gw = 160
    gx = PX + (PW - gw) // 2
    d.rectangle([gx, goal_y - 4, gx + gw, goal_y + 4], fill=WHITE)
    d.rectangle([gx - 8, goal_y - 70, gx + 8, goal_y], fill=WHITE)
    d.rectangle([gx + gw - 8, goal_y - 70, gx + gw + 8, goal_y], fill=WHITE)
    d.rectangle([gx - 8, goal_y - 70, gx + gw + 8, goal_y - 62], fill=WHITE)

    # 6-yard box
    sb_w, sb_h = 260, 160
    sb_x = PX + (PW - sb_w) // 2
    d.rectangle([sb_x, goal_y - sb_h, sb_x + sb_w, goal_y], outline=LINE, width=2)
    # 18-yard box (penalty area)
    pa_w, pa_h = 580, 290
    pa_x = PX + (PW - pa_w) // 2
    d.rectangle([pa_x, goal_y - pa_h, pa_x + pa_w, goal_y], outline=LINE, width=2)
    # Halfway line context
    d.line([PX, PY + PH // 2, PX + PW, PY + PH // 2], fill=LINE, width=1)

    # Penalty spot
    ps_x = PX + PW // 2
    ps_y = goal_y - 280
    r = 10
    d.ellipse([ps_x - r, ps_y - r, ps_x + r, ps_y + r], fill=WHITE)
    # D-arc
    arc_r = 130
    d.arc([ps_x - arc_r, ps_y - arc_r, ps_x + arc_r, ps_y + arc_r],
          start=230, end=310, fill=LINE, width=3)

    # ── Players ──────────────────────────────────────────────────────────────
    pr = 28
    mal_x = ps_x - 180
    mal_y = ps_y - 100
    mat_x = mal_x + 80
    mat_y = mal_y + 25

    # Malouda (France)
    d.ellipse([mal_x - pr, mal_y - pr, mal_x + pr, mal_y + pr],
              fill=FR_BLUE, outline=WHITE, width=3)
    d.text((mal_x - 44, mal_y + pr + 8), "MALOUDA", font=f_p, fill=WHITE)
    # Materazzi (Italy)
    d.ellipse([mat_x - pr, mat_y - pr, mat_x + pr, mat_y + pr],
              fill=(0, 0, 170), outline=RED, width=4)
    d.text((mat_x - 52, mat_y + pr + 8), "MATERAZZI", font=f_p, fill=RED)
    # Foul X
    cx, cy = (mal_x + mat_x) // 2, (mal_y + mat_y) // 2
    d.line([cx - 14, cy - 14, cx + 14, cy + 14], fill=RED, width=5)
    d.line([cx + 14, cy - 14, cx - 14, cy + 14], fill=RED, width=5)

    # Dashed arrow foul → penalty spot
    steps = 14
    for i in range(0, steps, 2):
        t0 = i / steps; t1 = (i + 1) / steps
        d.line([int(cx + (ps_x - cx)*t0), int(cy + (ps_y - cy)*t0),
                int(cx + (ps_x - cx)*t1), int(cy + (ps_y - cy)*t1)],
               fill=GOLD, width=4)
    d.polygon([ps_x - 12, ps_y - 18, ps_x + 12, ps_y - 18, ps_x, ps_y + 4], fill=GOLD)

    # Kick direction from spot towards goal (blue)
    kx, ky = ps_x - 30, goal_y - 40
    for i in range(0, steps, 2):
        t0 = i / steps; t1 = (i + 1) / steps
        d.line([int(ps_x + (kx - ps_x)*t0), int(ps_y + (ky - ps_y)*t0),
                int(ps_x + (kx - ps_x)*t1), int(ps_y + (ky - ps_y)*t1)],
               fill=FR_BLUE, width=4)

    # ── Result text ───────────────────────────────────────────────────────────
    ry = PY + PH + 50
    draw_text_centered(d, ry,       "MATERAZZI FOULS MALOUDA", f_lbl, WHITE)
    draw_text_centered(d, ry + 72,  "FRANCE AWARDED A PENALTY", f_lbl, FR_BLUE)
    gold_rule(d, ry + 160)
    draw_text_centered(d, ry + 180, "ZIDANE SCORES.  FRA  1 – 0  ITA", fnt(_DIN, 72), GOLD)

    watermark(d)
    return img


# ── SHOT 4 — Materazzi Equalizer ──────────────────────────────────────────────
# Corner → header → goal: top-down diagram + live scoreline flip
def shot_04() -> Image.Image:
    img, d = new_frame(NAVY)

    f_hdr = fnt(_DIN, 72)
    f_lbl = fnt(_DIN, 52)
    f_scr = fnt(_DIN, 130)
    f_sm  = fnt(_AR,  34)

    draw_text_centered(d, 80, "19'  —  THE EQUALIZER", f_hdr, GOLD)
    gold_rule(d, 164)

    # ── Top-down header diagram ───────────────────────────────────────────────
    DX, DY, DW, DH = 90, 190, 900, 940
    d.rectangle([DX, DY, DX + DW, DY + DH], fill=PITCH)
    d.rectangle([DX, DY, DX + DW, DY + DH], outline=LINE, width=3)

    # Goal mouth (bottom-center)
    goal_y = DY + DH
    gw     = 150
    gx     = DX + (DW - gw) // 2
    d.rectangle([gx - 6, goal_y - 60, gx + gw + 6, goal_y - 54], fill=WHITE)
    d.rectangle([gx - 6, goal_y - 60, gx + 6, goal_y], fill=WHITE)
    d.rectangle([gx + gw - 6, goal_y - 60, gx + gw + 6, goal_y], fill=WHITE)
    d.rectangle([gx, goal_y - 4, gx + gw, goal_y + 4], fill=WHITE)
    # 6-yard box
    sb_w, sb_h = 230, 110
    sb_x = DX + (DW - sb_w) // 2
    d.rectangle([sb_x, DY + DH - sb_h, sb_x + sb_w, DY + DH], outline=LINE, width=2)
    # 18-yard box
    d.rectangle([DX + 50, DY + 300, DX + DW - 50, DY + DH], outline=LINE, width=2)
    # Penalty spot
    ps_x = DX + DW // 2
    ps_y = DY + DH - 230
    d.ellipse([ps_x - 6, ps_y - 6, ps_x + 6, ps_y + 6], fill=WHITE)
    # Corner flag (top-right)
    cf_x, cf_y = DX + DW - 30, DY + 30
    d.ellipse([cf_x - 8, cf_y - 8, cf_x + 8, cf_y + 8], fill=GOLD, outline=WHITE, width=2)
    d.text((cf_x - 50, cf_y - 36), "CORNER", font=fnt(_AR, 22), fill=GOLD)

    # Pirlo (ball source at corner)
    pr_x, pr_y = cf_x, cf_y + 60
    pr = 20
    d.ellipse([pr_x - pr, pr_y - pr, pr_x + pr, pr_y + pr], fill=(0, 0, 180), outline=WHITE, width=2)
    d.text((pr_x + pr + 6, pr_y - 10), "PIRLO", font=fnt(_AR, 22), fill=WHITE)

    # Materazzi header position (penalty spot area, center of box)
    mat_x = DX + DW // 2 - 20
    mat_y = DY + DH - 310
    pr2 = 24
    d.ellipse([mat_x - pr2, mat_y - pr2, mat_x + pr2, mat_y + pr2],
              fill=(0, 0, 170), outline=GOLD, width=3)
    d.text((mat_x - 46, mat_y + pr2 + 6), "MATERAZZI", font=fnt(_AR, 22), fill=GOLD)

    # Vieira being jumped (slightly behind Materazzi)
    vie_x = mat_x + 50
    vie_y = mat_y + 20
    d.ellipse([vie_x - 18, vie_y - 18, vie_x + 18, vie_y + 18],
              fill=FR_BLUE, outline=WHITE, width=2)
    d.text((vie_x + 22, vie_y - 10), "VIEIRA", font=fnt(_AR, 20), fill=LIGHT)

    # Ball arc: corner → Materazzi → goal
    # Phase 1: corner → header
    arc_steps = 20
    # Bezier-style curve via intermediate points
    ctrl_x = DX + DW // 2 - 60
    ctrl_y = DY + 80  # top of arc
    for i in range(arc_steps):
        t  = i / arc_steps
        t1 = (i + 1) / arc_steps
        # Quadratic bezier
        bx0 = int((1-t)**2 * pr_x + 2*(1-t)*t * ctrl_x + t**2 * mat_x)
        by0 = int((1-t)**2 * pr_y + 2*(1-t)*t * ctrl_y + t**2 * mat_y)
        bx1 = int((1-t1)**2 * pr_x + 2*(1-t1)*t1 * ctrl_x + t1**2 * mat_x)
        by1 = int((1-t1)**2 * pr_y + 2*(1-t1)*t1 * ctrl_y + t1**2 * mat_y)
        # Fade opacity along arc (draw as separate line segments → not rgba)
        d.line([bx0, by0, bx1, by1], fill=WHITE, width=3)
    # Ball dot at header point
    d.ellipse([mat_x - 10, mat_y - 10, mat_x + 10, mat_y + 10], fill=WHITE)
    # Phase 2: header → goal (powered header trajectory)
    goal_target_x = gx + gw // 2 - 30
    goal_target_y = goal_y - 20
    ctrl2_x = mat_x - 30
    ctrl2_y = DY + DH - 180
    for i in range(arc_steps):
        t  = i / arc_steps
        t1 = (i + 1) / arc_steps
        bx0 = int((1-t)**2 * mat_x + 2*(1-t)*t * ctrl2_x + t**2 * goal_target_x)
        by0 = int((1-t)**2 * mat_y + 2*(1-t)*t * ctrl2_y + t**2 * goal_target_y)
        bx1 = int((1-t1)**2 * mat_x + 2*(1-t1)*t1 * ctrl2_x + t1**2 * goal_target_x)
        by1 = int((1-t1)**2 * mat_y + 2*(1-t1)*t1 * ctrl2_y + t1**2 * goal_target_y)
        d.line([bx0, by0, bx1, by1], fill=GOLD, width=4)
    # Arrowhead at goal
    d.polygon([goal_target_x - 10, goal_target_y - 2,
               goal_target_x + 10, goal_target_y - 2,
               goal_target_x, goal_target_y + 14], fill=GOLD)

    # ── Scoreline ─────────────────────────────────────────────────────────────
    score_y = DY + DH + 55
    # France flag swatch
    fw = 90
    d.rectangle([140, score_y, 140 + fw // 3, score_y + 60], fill=FR_BLUE)
    d.rectangle([140 + fw // 3, score_y, 140 + 2 * fw // 3, score_y + 60], fill=WHITE)
    d.rectangle([140 + 2 * fw // 3, score_y, 140 + fw, score_y + 60], fill=FR_RED)
    # Italy flag swatch
    ix = W - 140 - fw
    d.rectangle([ix, score_y, ix + fw // 3, score_y + 60], fill=IT_GRN)
    d.rectangle([ix + fw // 3, score_y, ix + 2 * fw // 3, score_y + 60], fill=WHITE)
    d.rectangle([ix + 2 * fw // 3, score_y, ix + fw, score_y + 60], fill=IT_RED)

    # Score
    draw_text_centered(d, score_y - 10, "1  —  1", f_scr, WHITE)
    # Country labels
    f_cn = fnt(_DIN, 50)
    d.text((140, score_y + 70), "FRANCE", font=f_cn, fill=LIGHT)
    bb = d.textbbox((0, 0), "ITALY", font=f_cn)
    d.text((W - 140 - (bb[2]-bb[0]), score_y + 70), "ITALY", font=f_cn, fill=LIGHT)

    draw_text_centered(d, score_y + 150, "MATERAZZI HEADER · PIRLO CORNER · 19'", f_lbl, GOLD)

    watermark(d)
    return img


# ── SHOT 5 — Bridge (Zidane/Thuram, 108' badge) ───────────────────────────────
def shot_05() -> Image.Image:
    base = photo_fill(PHOTOS / "zidane_thuram_final_cc_by_2.0.jpg")
    base = add_overlay(base, NAVY2, opacity=0.35)

    img = base.copy()
    d   = ImageDraw.Draw(img)

    # Top bar
    d.rectangle([0, 0, W, 90], fill=(*NAVY2, 220))
    f_top = fnt(_DIN, 46)
    draw_text_centered(d, 22, "2006 FIFA WORLD CUP FINAL · EXTRA TIME", f_top, LIGHT)

    # Prominent "108'" badge
    bw, bh = 300, 110
    bx = (W - bw) // 2
    by = H // 2 - 200
    d.rectangle([bx, by, bx + bw, by + bh], fill=NAVY2)
    d.rectangle([bx, by, bx + bw, by + bh], outline=GOLD, width=4)
    f_min = fnt(_DIN, 90)
    draw_text_centered(d, by + 10, "108'", f_min, GOLD)

    # Tension text below
    f_tension = fnt(_DIN, 60)
    draw_text_centered(d, by + bh + 50, "MATERAZZI SAYS SOMETHING.", f_tension, WHITE)

    watermark(d)
    return img


# ── SHOT 6 — Headbutt card ────────────────────────────────────────────────────
# Pure black, white HEADBUTT., red RED CARD.
# (The subsequent Zidane photo with filter is a different edit state; show text version)
def shot_06() -> Image.Image:
    img, d = new_frame(BLACK)

    f_impact = fnt(_DIN, 160)
    f_rc     = fnt(_DIN, 130)
    f_sub    = fnt(_AR,   42)

    # Build up: each word drops in
    h1 = draw_text_centered(d, H // 2 - 220, "HEADBUTT.", f_impact, WHITE, shadow_col=(80, 0, 0))
    draw_text_centered(d, H // 2 - 220 + h1 + 24, "RED CARD.", f_rc, RED, shadow_col=BLACK)

    # Referee silhouette (simple geometric figure)
    rx, ry = W // 2 + 240, H // 2 + 120
    # Body
    d.ellipse([rx - 25, ry - 90, rx + 25, ry - 40], fill=(220, 220, 220))  # head
    d.rectangle([rx - 20, ry - 40, rx + 20, ry + 60], fill=(220, 220, 220))  # torso
    d.rectangle([rx - 20, ry + 60, rx - 5,  ry + 130], fill=(220, 220, 220))  # left leg
    d.rectangle([rx + 5,  ry + 60, rx + 20, ry + 130], fill=(220, 220, 220))  # right leg
    # Raised arm with red card
    arm_x1, arm_y1 = rx + 20, ry - 20
    arm_x2, arm_y2 = rx + 80, ry - 100
    d.line([arm_x1, arm_y1, arm_x2, arm_y2], fill=(220, 220, 220), width=12)
    # Red card rectangle
    d.rectangle([arm_x2 - 18, arm_y2 - 36, arm_x2 + 18, arm_y2 + 4], fill=RED)

    # Zidane walk-off silhouette (smaller, left side, hunched)
    zx, zy = W // 2 - 220, H // 2 + 80
    d.ellipse([zx - 20, zy - 80, zx + 20, zy - 40], fill=GREY)
    d.line([zx, zy - 40, zx - 15, zy + 60], fill=GREY, width=16)  # torso (hunched)
    d.line([zx - 15, zy + 60, zx - 20, zy + 130], fill=GREY, width=10)
    d.line([zx - 15, zy + 60, zx + 5,  zy + 130], fill=GREY, width=10)

    # Context label
    draw_text_centered(d, H // 2 + 320,
                       "Zidane's last act as a professional footballer.", f_sub, GREY)

    watermark(d)
    return img


# ── SHOT 7 — Penalty shootout graphic ─────────────────────────────────────────

def _result_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, scored: bool, r: int = 24) -> None:
    """Draw a solid circle with a check or X — no Unicode required."""
    if scored:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 160, 60))
        # Checkmark: two lines forming a V
        draw.line([cx - r//2, cy, cx - r//8, cy + r//2], fill=WHITE, width=5)
        draw.line([cx - r//8, cy + r//2, cx + r//2, cy - r//3], fill=WHITE, width=5)
    else:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
        draw.line([cx - r//2, cy - r//2, cx + r//2, cy + r//2], fill=WHITE, width=5)
        draw.line([cx + r//2, cy - r//2, cx - r//2, cy + r//2], fill=WHITE, width=5)


def shot_07() -> Image.Image:
    img, d = new_frame(NAVY)

    f_hdr  = fnt(_DIN, 72)
    f_name = fnt(_DIN, 60)
    f_cn   = fnt(_DIN, 50)
    f_scr  = fnt(_DIN, 120)
    f_note = fnt(_AR,  28)

    draw_text_centered(d, 60, "THE PENALTY SHOOTOUT", f_hdr, GOLD)
    gold_rule(d, 150)

    col_w = 460
    fr_x  = 50
    it_x  = W - 50 - col_w
    tbl_y = 175
    row_h = 148   # taller rows — fills the frame

    # ── France header flag ────────────────────────────────────────────────────
    hh = 72
    d.rectangle([fr_x,              tbl_y, fr_x + col_w//3,     tbl_y + hh], fill=FR_BLUE)
    d.rectangle([fr_x + col_w//3,   tbl_y, fr_x + 2*col_w//3,  tbl_y + hh], fill=WHITE)
    d.rectangle([fr_x + 2*col_w//3, tbl_y, fr_x + col_w,       tbl_y + hh], fill=FR_RED)
    fr_bb = d.textbbox((0,0), "FRANCE", font=f_cn)
    d.text((fr_x + (col_w - (fr_bb[2]-fr_bb[0]))//2, tbl_y + 16), "FRANCE", font=f_cn, fill=NAVY)

    # ── Italy header flag ─────────────────────────────────────────────────────
    d.rectangle([it_x,              tbl_y, it_x + col_w//3,     tbl_y + hh], fill=IT_GRN)
    d.rectangle([it_x + col_w//3,   tbl_y, it_x + 2*col_w//3,  tbl_y + hh], fill=WHITE)
    d.rectangle([it_x + 2*col_w//3, tbl_y, it_x + col_w,       tbl_y + hh], fill=IT_RED)
    it_bb = d.textbbox((0,0), "ITALY", font=f_cn)
    d.text((it_x + (col_w - (it_bb[2]-it_bb[0]))//2, tbl_y + 16), "ITALY", font=f_cn, fill=WHITE)

    france_takers = [
        ("WILTORD",   True),
        ("TREZEGUET", False),
        ("ABIDAL",    True),
        ("SAGNOL",    True),
    ]
    italy_takers = [
        ("PIRLO",     True),
        ("MATERAZZI", True),
        ("DE ROSSI",  True),
        ("DEL PIERO", True),
        ("GROSSO",    True),
    ]

    rows_start = tbl_y + hh + 4

    for i, (name, scored) in enumerate(france_takers):
        ry  = rows_start + i * row_h
        bg  = (18, 45, 95) if scored else (55, 16, 16)
        d.rectangle([fr_x, ry, fr_x + col_w, ry + row_h - 4], fill=bg)
        d.text((fr_x + 18, ry + (row_h - 60)//2), name, font=f_name, fill=WHITE)
        _result_mark(d, fr_x + col_w - 40, ry + row_h//2 - 2, scored)
        if name == "TREZEGUET":
            d.text((fr_x + 18, ry + row_h - 34), "HIT THE CROSSBAR",
                   font=f_note, fill=(255, 100, 100))

    for i, (name, scored) in enumerate(italy_takers):
        ry = rows_start + i * row_h
        is_mat = (name == "MATERAZZI")
        if is_mat:
            d.rectangle([it_x - 4, ry - 4, it_x + col_w + 4, ry + row_h], fill=GOLD)
            d.rectangle([it_x, ry, it_x + col_w, ry + row_h - 4], fill=(22, 55, 18))
            d.text((it_x + 18, ry + (row_h - 60)//2), name, font=f_name, fill=GOLD)
        else:
            d.rectangle([it_x, ry, it_x + col_w, ry + row_h - 4], fill=(18, 65, 28))
            d.text((it_x + 18, ry + (row_h - 60)//2), name, font=f_name, fill=WHITE)
        _result_mark(d, it_x + col_w - 40, ry + row_h//2 - 2, scored)

    # ── Final score ───────────────────────────────────────────────────────────
    score_y = rows_start + 5 * row_h + 30
    gold_rule(d, score_y)
    draw_text_centered(d, score_y + 24, "ITALY  5  –  3  FRANCE", f_scr, WHITE)
    draw_text_centered(d, score_y + 164, "ITALY WIN THE 2006 FIFA WORLD CUP",
                       fnt(_DIN, 52), GOLD)

    watermark(d)
    return img


# ── SHOT 8 — Kicker: three facts, no subjective claims ────────────────────────
def shot_08() -> Image.Image:
    base = photo_fill(PHOTOS / "materazzi_cc_by_2.0.jpg")
    base = ImageEnhance.Sharpness(base).enhance(1.4)
    base = add_overlay(base, NAVY2, opacity=0.72)

    img = base.copy()
    d   = ImageDraw.Draw(img)

    f_top  = fnt(_DIN, 56)
    f_fact = fnt(_DIN, 76)
    f_kick = fnt(_DIN, 68)
    f_sm   = fnt(_AR,  34)

    # Three bullet facts (Materazzi's three contributions)
    draw_text_centered(d, 160, "THREE CONTRIBUTIONS.", f_top, GOLD)
    gold_rule(d, 250)

    facts = [
        ("1  FOUL",    "CONCEDED FRANCE'S OPENING PENALTY"),
        ("1  GOAL",    "HEADED IN ITALY'S EQUALIZER — 19'"),
        ("1  PENALTY", "SCORED IN THE SHOOTOUT — ITALY WON"),
    ]
    fy = 310
    for icon, detail in facts:
        # Bullet box
        d.rectangle([80, fy, 80 + 260, fy + 80], fill=GOLD)
        f_ico = fnt(_DIN, 58)
        d.text((100, fy + 12), icon, font=f_ico, fill=NAVY)
        # Detail text
        d.text((360, fy + 18), detail, font=fnt(_DIN, 46), fill=WHITE)
        fy += 110

    gold_rule(d, fy + 20)

    # Kicker lines
    draw_text_centered(d, fy + 60,  "HIS NAME IS ONLY EVER", f_kick, WHITE)
    draw_text_centered(d, fy + 140, "MENTIONED FOR THE HEADBUTT.", f_kick, GOLD)

    watermark(d)
    return img


# ── SHOT 9 — Brand card ────────────────────────────────────────────────────────
def shot_09() -> Image.Image:
    img, d = new_frame(NAVY2)

    f_brand  = fnt(_DIN, 110)
    f_tag    = fnt(_DIN,  56)
    f_follow = fnt(_AR,   38)

    # Vertically center: total content block ≈ 460px
    block_h = 460
    top     = (H - block_h) // 2  # ~730

    gold_rule(d, top, margin=80)
    draw_text_centered(d, top + 24,       "BEYOND",    f_brand, GOLD)
    draw_text_centered(d, top + 24 + 118, "THE PITCH", f_brand, WHITE)
    gold_rule(d, top + 268, margin=80)
    draw_text_centered(d, top + 294, "Football stories you've forgotten.", f_tag, LIGHT)
    draw_text_centered(d, top + 374, "Follow for more  ↑",                 f_follow, GREY)

    return img


# ── Contact sheet ─────────────────────────────────────────────────────────────

def make_contact_sheet(frames: list[Image.Image]) -> Image.Image:
    """3×3 grid, 1080×1920. Each thumbnail 360×640."""
    sheet = Image.new("RGB", (W, H), (20, 20, 25))
    d     = ImageDraw.Draw(sheet)
    cols, rows = 3, 3
    tw = W // cols   # 360
    th = H // rows   # 640

    for i, frame in enumerate(frames[:9]):
        col = i % cols
        row = i // cols
        thumb = frame.resize((tw, th), Image.LANCZOS)
        sheet.paste(thumb, (col * tw, row * th))
        # Thin border between cells
        bx, by = col * tw, row * th
        d.rectangle([bx, by, bx + tw - 1, by + th - 1], outline=GOLD, width=1)
        # Shot number badge
        f_n = fnt(_DIN, 36)
        badge_text = f"S{i+1}"
        d.rectangle([bx + 6, by + 6, bx + 60, by + 42], fill=GOLD)
        d.text((bx + 10, by + 6), badge_text, font=f_n, fill=NAVY)

    return sheet


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    generators = [shot_01, shot_02, shot_03, shot_04, shot_05,
                  shot_06, shot_07, shot_08, shot_09]
    frames = []
    for i, gen in enumerate(generators, 1):
        print(f"  Generating shot {i}…", end=" ", flush=True)
        frame = gen()
        path  = GFXDIR / f"shot_{i:02d}.png"
        frame.save(str(path), "PNG", optimize=False)
        frames.append(frame)
        print(f"saved → {path.name}")

    print("  Composing contact sheet…", end=" ", flush=True)
    sheet = make_contact_sheet(frames)
    sheet_path = OUT / "storyboard_contact_sheet.png"
    sheet.save(str(sheet_path), "PNG")
    print(f"saved → {sheet_path.name}")

    print(f"\nDone. {len(frames)} frames + contact sheet in:")
    print(f"  {OUT}")


if __name__ == "__main__":
    main()
