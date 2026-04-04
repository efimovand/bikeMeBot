import asyncio
from pathlib import Path
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, selectinload

from models import Helmet, Jacket
from config import settings
import database as db


# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

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

# Настройки для каждого типа: директория сохранения + иконка (на будущее)
TYPE_CONFIG = {
    "helmet": {"dir": BASE_DIR / "collages/helmets", "prefix": "helmets"},
    "jacket": {"dir": BASE_DIR / "collages/jackets", "prefix": "jackets"},
    # "glove":  {"dir": BASE_DIR / "collages/gloves",  "prefix": "gloves"},
    # "boot":   {"dir": BASE_DIR / "collages/boots",   "prefix": "boots"},
}


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
# RENDER
# -------------------------------------------------------------------

def _fill_crop(img: Image.Image, w: int, h: int) -> Image.Image:
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


def _draw_card(model_name: str, brand_name: str, photo_path: str | None) -> Image.Image:
    card = Image.new("RGB", (CARD_SIZE, CARD_SIZE), (255, 255, 255))
    photo_h = CARD_SIZE - PLATE_H

    if photo_path:
        try:
            photo = load_image(photo_path).convert("RGBA")
            photo = _fill_crop(photo, CARD_SIZE, photo_h)
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
    draw.text((20, photo_h + 6), brand_name.upper(), font=font_brand, fill=TEXT_ACCENT)
    name = _truncate(draw, model_name, font_model, CARD_SIZE - 18)
    draw.text((10, photo_h + 21), name, font=font_model, fill=TEXT_PRIMARY)

    return card


# -------------------------------------------------------------------
# DTO
# -------------------------------------------------------------------

class ItemView:
    def __init__(self, model: str, photo_path: str | None):
        self.model = model
        self.photo_path = photo_path


# -------------------------------------------------------------------
# DB → DTO (по типу)
# -------------------------------------------------------------------

def _fetch_items(session: Session, type: str, brand: str) -> list[ItemView]:
    if type == "helmet":
        rows = (
            session.query(Helmet)
            .options(selectinload(Helmet.files))
            .filter(Helmet.brand == brand)
            .order_by(Helmet.model)
            .all()
        )
        return [ItemView(h.model, h.files[0].file if h.files else None) for h in rows]

    if type == "jacket":
        rows = (
            session.query(Jacket)
            .options(selectinload(Jacket.files))
            .filter(Jacket.brand == brand)
            .order_by(Jacket.model)
            .all()
        )
        return [ItemView(j.model, j.files[0].file if j.files else None) for j in rows]

    # if type == "glove": ...
    # if type == "boot":  ...

    raise ValueError(f"Unknown collage type: {type}")


# -------------------------------------------------------------------
# BUILD
# -------------------------------------------------------------------

def _build_collage(items: list[ItemView], brand_name: str, type: str) -> Path:
    cfg = TYPE_CONFIG[type]
    collage_dir: Path = cfg["dir"]
    collage_dir.mkdir(parents=True, exist_ok=True)

    rows = -(-len(items) // COLS)
    w = COLS * CARD_SIZE + (COLS - 1) * GAP + PADDING * 2
    h = rows * CARD_SIZE + (rows - 1) * GAP + PADDING * 2

    canvas = Image.new("RGB", (w, h), BG_COLOR)

    for idx, item in enumerate(items):
        col, row = idx % COLS, idx // COLS
        x = PADDING + col * (CARD_SIZE + GAP)
        y = PADDING + row * (CARD_SIZE + GAP)
        canvas.paste(_draw_card(item.model, brand_name, item.photo_path), (x, y))

    slug = brand_name.lower().replace(" ", "_")
    filepath = collage_dir / f"{cfg['prefix']}_{slug}.jpg"
    canvas.save(filepath, "JPEG", quality=100, optimize=True)
    return filepath


# -------------------------------------------------------------------
# PUBLIC API
# -------------------------------------------------------------------

async def get_or_build_collage(type: str, brand: str) -> Path:
    current_count, cached_file, cached_count = await db.get_collage_state(type, brand)

    if cached_file and cached_count == current_count:
        path = Path(cached_file)
        if path.exists():
            return path

    sync_engine = create_engine(settings.database_url_sync)

    def _generate():
        with Session(sync_engine) as session:
            items = _fetch_items(session, type, brand)
        return _build_collage(items, brand, type)

    path = await asyncio.get_event_loop().run_in_executor(None, _generate)
    await db.upsert_collage(type, brand, str(path), current_count)
    return path
