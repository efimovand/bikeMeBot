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
GAP = 16
PADDING = 24

BG_COLOR = (15, 25, 35)
CARD_BG = (25, 35, 45)
CARD_BORDER = (40, 50, 60)
TEXT_PRIMARY = (220, 231, 240)
TEXT_ACCENT = (232, 102, 10)
ACCENT_LINE_C = (232, 102, 10)

PLATE_H = 70
CORNER_RADIUS = 12

FONT_BOLD_PATH = None
FONT_REGULAR_PATH = None

TYPE_SUBDIR = {
    "helmet": "helmets",
    "jacket": "jackets",
    "suit":   "suits",
    "glove":  "gloves",
    "boot":   "boots",
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
    candidates = [
        path,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


font_brand = _load_font(FONT_REGULAR_PATH, 16)
font_model = _load_font(FONT_BOLD_PATH, 22)


# -------------------------------------------------------------------
# IMAGE LOADER
# -------------------------------------------------------------------

def load_image(path: str) -> Image.Image:
    if not path:
        raise ValueError("Empty image path")
    if path.startswith("http"):
        headers = {"User-Agent": "Mozilla/5.0 CollageGenerator/1.0"}
        resp = requests.get(path, timeout=10, headers=headers)
        return Image.open(BytesIO(resp.content))
    full_path = BASE_DIR / Path(path)
    if not full_path.exists():
        raise FileNotFoundError(f"Not found: {full_path}")
    return Image.open(full_path)


# -------------------------------------------------------------------
# RENDER HELPERS
# -------------------------------------------------------------------

def _fit_on_white(img: Image.Image, w: int, h: int) -> Image.Image:
    """Вписывает изображение в заданный размер на чисто БЕЛЫЙ фон."""
    ratio = min(w / img.width, h / img.height) * 0.85
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)

    bg = Image.new("RGB", (w, h), (255, 255, 255))
    x, y = (w - nw) // 2, (h - nh) // 2

    if img.mode == "RGBA":
        bg.paste(img, (x, y), img)
    else:
        bg.paste(img, (x, y))
    return bg


def _truncate(draw, text, font, max_w):
    """Отрезает текст, если он не влезает, добавляя многоточие."""
    if draw.textlength(text, font=font) <= max_w:
        return text

    while draw.textlength(text + "...", font=font) > max_w and len(text) > 1:
        text = text[:-1]
    return text.rstrip() + "..."


def _draw_card(label_top: str, label_bottom: str, photo_path: str | None) -> Image.Image:
    """Белый фон под фото + темный подвал для текста."""
    card = Image.new("RGBA", (CARD_SIZE, CARD_SIZE), (255, 255, 255))
    draw = ImageDraw.Draw(card)

    photo_h = CARD_SIZE - PLATE_H

    if photo_path:
        try:
            photo = load_image(photo_path).convert("RGBA")
            photo_fitted = _fit_on_white(photo, CARD_SIZE, photo_h)
            card.paste(photo_fitted, (0, 0))
        except Exception as e:
            print(f"Error loading image: {e}")

    draw.rectangle([(0, photo_h), (CARD_SIZE, CARD_SIZE)], fill=BG_COLOR)

    draw.line([(0, photo_h), (CARD_SIZE, photo_h)], fill=TEXT_ACCENT, width=2)

    text_w_limit = CARD_SIZE - 30

    brand_txt = _truncate(draw, label_top.upper(), font_brand, text_w_limit)
    draw.text((15, photo_h + 10), brand_txt, font=font_brand, fill=TEXT_ACCENT)

    model_txt = _truncate(draw, label_bottom, font_model, text_w_limit)
    draw.text((15, photo_h + 32), model_txt, font=font_model, fill=TEXT_PRIMARY)

    mask = Image.new("L", (CARD_SIZE, CARD_SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, CARD_SIZE, CARD_SIZE), CORNER_RADIUS, fill=255)

    final_card = Image.new("RGBA", (CARD_SIZE, CARD_SIZE), (0, 0, 0, 0))
    final_card.paste(card, (0, 0), mask=mask)

    final_draw = ImageDraw.Draw(final_card)
    final_draw.rounded_rectangle((0, 0, CARD_SIZE - 1, CARD_SIZE - 1), CORNER_RADIUS, outline=CARD_BORDER, width=1)

    return final_card


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

        card_img = _draw_card(item.label_top, item.label_bottom, item.photo_path)

        canvas.paste(card_img, (x, y), card_img)

    canvas.save(out_path, "JPEG", quality=95, optimize=True)
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
