import asyncio
from pathlib import Path
from io import BytesIO
from typing import NamedTuple
import requests
from PIL import Image, ImageDraw, ImageFont
import database as db


BASE_DIR = Path(__file__).resolve().parent / "media"

CARD_SIZE = 400
COLS = 3
GAP = 8
PADDING = 12

BG_COLOR = (15, 25, 35)
ACCENT = (232, 102, 10)
PLATE_BG = (10, 18, 27, 215)
TEXT_PRIMARY = (220, 231, 240)
TEXT_ACCENT = (232, 102, 10)
PLATE_H = 46

FONT_BOLD_PATH = None
FONT_REGULAR_PATH = None

TYPE_SUBDIR = {
    "helmet": "helmets",
    "jacket": "jackets",
    "glove":  "gloves",
}


def _brand_dir(item_type: str, brand: str) -> Path:
    slug = brand.lower().replace(" ", "_")
    path = BASE_DIR / "collages" / TYPE_SUBDIR[item_type] / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


# -------------------------------------------------------------------
# FONTS
# -------------------------------------------------------------------

def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except OSError:
        return ImageFont.load_default()


font_brand = _load_font(FONT_BOLD_PATH, 10)
font_model = _load_font(FONT_REGULAR_PATH, 13)


# -------------------------------------------------------------------
# IMAGE LOADER
# -------------------------------------------------------------------

def load_image(path: str) -> Image.Image:
    if not path:
        raise ValueError("Empty image path")
    if path.startswith("http"):
        resp = requests.get(path, timeout=5)
        return Image.open(BytesIO(resp.content))
    full_path = BASE_DIR / Path(path)
    if not full_path.exists():
        raise FileNotFoundError(f"Not found: {full_path}")
    return Image.open(full_path)


# -------------------------------------------------------------------
# RENDER HELPERS
# -------------------------------------------------------------------

def _fit_on_white(img: Image.Image, w: int, h: int) -> Image.Image:
    ratio = min(w / img.width, h / img.height) * 0.85
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    bg = Image.new("RGB", (w, h), (255, 255, 255))
    x, y = (w - nw) // 2, (h - nh) // 2
    bg.paste(img, (x, y), img) if img.mode == "RGBA" else bg.paste(img, (x, y))
    return bg


def _draw_triangle(draw, x, y, size, color):
    draw.polygon([(x + size // 2, y), (x + size, y + size), (x, y + size)], fill=color)


def _truncate(draw, text, font, max_w):
    while draw.textlength(text, font=font) > max_w and len(text) > 1:
        text = text[:-1]
    return text.rstrip()


def _draw_card(label_top: str, label_bottom: str, photo_path: str | None) -> Image.Image:
    card = Image.new("RGB", (CARD_SIZE, CARD_SIZE), (255, 255, 255))
    photo_h = CARD_SIZE - PLATE_H

    if photo_path:
        try:
            photo = load_image(photo_path).convert("RGBA")
            photo = _fit_on_white(photo, CARD_SIZE, photo_h)
            card.paste(photo, (0, 0))
        except Exception as e:
            print("Image error:", e)

    grad = Image.new("RGBA", (CARD_SIZE, 32), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(32):
        gd.line([(0, i), (CARD_SIZE, i)], fill=(0, 0, 0, int(170 * i / 32)))
    card_rgba = card.convert("RGBA")
    card_rgba.paste(grad, (0, photo_h - 10), grad)
    card = card_rgba.convert("RGB")

    overlay = Image.new("RGBA", (CARD_SIZE, PLATE_H), PLATE_BG)
    card_rgba = card.convert("RGBA")
    card_rgba.paste(overlay, (0, photo_h), overlay)
    card = card_rgba.convert("RGB")

    draw = ImageDraw.Draw(card)
    draw.line([(0, photo_h), (CARD_SIZE, photo_h)], fill=ACCENT, width=2)
    _draw_triangle(draw, 10, photo_h + 7, 6, ACCENT)
    draw.text((20, photo_h + 6), label_top.upper(), font=font_brand, fill=TEXT_ACCENT)
    name = _truncate(draw, label_bottom, font_model, CARD_SIZE - 18)
    draw.text((10, photo_h + 21), name, font=font_model, fill=TEXT_PRIMARY)

    return card


# -------------------------------------------------------------------
# BUILD
# -------------------------------------------------------------------

class ItemView(NamedTuple):
    label_top: str
    label_bottom: str
    photo_path: str | None


def _build_collage(items: list[ItemView], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = -(-len(items) // COLS)
    w = COLS * CARD_SIZE + (COLS - 1) * GAP + PADDING * 2
    h = rows * CARD_SIZE + (rows - 1) * GAP + PADDING * 2

    canvas = Image.new("RGB", (w, h), BG_COLOR)

    for idx, item in enumerate(items):
        col, row = idx % COLS, idx // COLS
        x = PADDING + col * (CARD_SIZE + GAP)
        y = PADDING + row * (CARD_SIZE + GAP)
        canvas.paste(_draw_card(item.label_top, item.label_bottom, item.photo_path), (x, y))

    canvas.save(out_path, "JPEG", quality=100, optimize=True)
    return out_path


# -------------------------------------------------------------------
# PUBLIC API
# -------------------------------------------------------------------

async def get_or_build_brand_collage(item_type: str, brand: str) -> Path:
    current_count, cached_file, cached_count = await db.get_brand_collage_state(item_type, brand)

    if cached_file and cached_count == current_count:
        path = Path(cached_file)
        if path.exists():
            return path

    raw_items = await db.get_items_for_collage(item_type, brand)
    items = [ItemView(brand, model, photo) for model, photo in raw_items]

    out_path = _brand_dir(item_type, brand) / "models.jpg"

    def _generate():
        return _build_collage(items, out_path)

    path = await asyncio.get_running_loop().run_in_executor(None, _generate)
    await db.upsert_brand_collage(item_type, brand, str(path), current_count)
    return path


async def get_or_build_color_collage(item_type: str, brand: str, model_id: int, model_name: str) -> Path:
    current_count, cached_file, cached_count = await db.get_color_collage_state(item_type, brand, model_id)

    if cached_file and cached_count == current_count:
        path = Path(cached_file)
        if path.exists():
            return path

    raw_items = await db.get_colors_for_collage(item_type, model_id)
    items = [ItemView(model_name, color_name, photo) for color_name, photo in raw_items]

    slug = model_name.lower().replace(" ", "_")
    out_path = _brand_dir(item_type, brand) / f"colors_{slug}.jpg"

    def _generate():
        return _build_collage(items, out_path)

    path = await asyncio.get_running_loop().run_in_executor(None, _generate)
    await db.upsert_color_collage(item_type, brand, model_id, str(path), current_count)
    return path