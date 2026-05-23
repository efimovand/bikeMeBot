"""
Генерирует коллажи каталога экипировки и байков.
Результат: media/collages/<type>/<brand_slug>/models.jpg, colors_<model_slug>.jpg

Запуск:
    python collage.py                               # все типы, все бренды
    python collage.py --type bike                   # только байки
    python collage.py --type helmet --brand AGV     # конкретный бренд
    python collage.py --force                       # пересоздать все (чистит кеш)
    python collage.py --type jacket --force         # пересоздать только куртки
"""


import asyncio
from pathlib import Path
from io import BytesIO
from typing import NamedTuple
import requests
from PIL import Image, ImageDraw, ImageFont, ImageChops
import database as db
import numpy as np


BASE_DIR = Path(__file__).resolve().parent / "media"


CARD_SIZE = 400
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
    "bike":    "bikes",
    "helmet":  "helmets",
    "jacket":  "jackets",
    "suit":    "suits",
    "glove":   "gloves",
    "boot":    "boots",
}


def _brand_dir(item_type: str, brand: str) -> Path:
    slug = brand.lower().replace(" ", "_")
    path = BASE_DIR / "collages" / TYPE_SUBDIR[item_type] / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


# FONTS
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


# IMAGE LOADER
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


# RENDER HELPERS
def _crop_to_content(img: Image.Image, bg_color=BG_COLOR, margin: int = 20) -> Image.Image:
    bg = Image.new("RGB", img.size, bg_color)
    diff = ImageChops.difference(img.convert("RGB"), bg)
    bbox = diff.convert("L").getbbox()
    if bbox is None:
        return img
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(img.width, x2 + margin)
    y2 = min(img.height, y2 + margin)
    return img.crop((x1, y1, x2, y2))


def _fit_on_white(img: Image.Image, w: int, h: int) -> Image.Image:
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


def _fit_on_dark(img: Image.Image, w: int, h: int) -> Image.Image:
    img = _crop_to_content(img)
    ratio = min(w / img.width, h / img.height) * 0.85
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)

    bg = Image.new("RGB", (w, h), BG_COLOR)
    x, y = (w - nw) // 2, (h - nh) // 2

    if img.mode == "RGBA":
        bg.paste(img, (x, y), img)
    else:
        bg.paste(img, (x, y))
    return bg


def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while draw.textlength(text + "...", font=font) > max_w and len(text) > 1:
        text = text[:-1]
    return text.rstrip() + "..."


def _draw_card(label_top: str, label_bottom: str, photo_path: str | None, dark_bg: bool = False) -> Image.Image:
    card_color = BG_COLOR if dark_bg else (255, 255, 255)
    card = Image.new("RGBA", (CARD_SIZE, CARD_SIZE), card_color)
    draw = ImageDraw.Draw(card)

    photo_h = CARD_SIZE - PLATE_H

    if photo_path:
        try:
            photo = load_image(photo_path).convert("RGBA")
            fitted = (_fit_on_dark if dark_bg else _fit_on_white)(photo, CARD_SIZE, photo_h)
            card.paste(fitted, (0, 0))
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


# BUILD
class ItemView(NamedTuple):
    label_top: str
    label_bottom: str
    photo_path: str | None


def _build_collage(items: list[ItemView], out_path: Path, dark_bg: bool = False) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cols = 4 if len(items) > 9 else 3
    rows = -(-len(items) // cols)
    w = cols * CARD_SIZE + (cols - 1) * GAP + PADDING * 2
    h = rows * CARD_SIZE + (rows - 1) * GAP + PADDING * 2

    canvas = Image.new("RGB", (w, h), BG_COLOR)

    for idx, item in enumerate(items):
        col, row = idx % cols, idx // cols
        x = PADDING + col * (CARD_SIZE + GAP)
        y = PADDING + row * (CARD_SIZE + GAP)

        card_img = _draw_card(item.label_top, item.label_bottom, item.photo_path, dark_bg=dark_bg)
        canvas.paste(card_img, (x, y), card_img)

    canvas.save(out_path, "JPEG", quality=95, optimize=True)
    return out_path


# PUBLIC API
async def get_or_build_brand_collage(item_type: str, brand: str) -> Path:
    current_count, cached_file, cached_count = await db.get_brand_collage_state(item_type, brand)

    if cached_file and cached_count == current_count:
        path = Path(cached_file)
        if path.exists():
            return path

    raw_items = await db.get_items_for_collage(item_type, brand)
    items = [ItemView(brand, model, photo) for model, photo in raw_items]

    if item_type == "bike":
        slug = brand.lower().replace(" ", "_")
        out_path = BASE_DIR / "collages" / "bikes" / f"{slug}_silhouettes.jpg"
        dark_bg = True
    else:
        out_path = _brand_dir(item_type, brand) / "models.jpg"
        dark_bg = False

    def _generate():
        return _build_collage(items, out_path, dark_bg=dark_bg)

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


# Ручной запуск
async def run_collage_batch(type_filter: str | None, brand_filter: str | None, force: bool):
    import database as db

    type_map = {
        "bike": db.get_bike_brands,
        "helmet": db.get_helmet_brands,
        "jacket": db.get_jacket_brands,
        "suit": db.get_suit_brands,
        "glove": db.get_glove_brands,
        "boot": db.get_boot_brands,
    }

    types = [type_filter] if type_filter else list(type_map.keys())

    if force:
        from sqlalchemy import delete
        from models import Collage
        async with db.get_session() as session:
            q = delete(Collage)
            if type_filter:
                q = q.where(Collage.type == type_filter)
            await session.execute(q)
        print("🗑  Кеш коллажей очищен.")

    ok = fail = 0

    for item_type in types:
        brands = await type_map[item_type]()
        if brand_filter:
            brands = [b for b in brands if brand_filter.lower() in b.lower()]

        for brand in brands:
            try:
                path = await get_or_build_brand_collage(item_type, brand)
                print(f"  ✅  {item_type} / {brand} → {path}")
                ok += 1
            except Exception as e:
                print(f"  ❌  {item_type} / {brand} — {e}")
                fail += 1

            # цветовые коллажи (не для байков)
            if item_type != "bike":
                raw_items = await db.get_items_for_collage(item_type, brand)
                model_getter = {
                    "helmet": db.get_helmet_models,
                    "jacket": db.get_jacket_models,
                    "suit":   db.get_suit_models,
                    "glove":  db.get_glove_models,
                    "boot":   db.get_boot_models,
                }[item_type]
                models = await model_getter(brand)
                for model in models:
                    try:
                        path = await get_or_build_color_collage(item_type, brand, model.id, model.model)
                        print(f"  ✅  {item_type} / {brand} / {model.model} colors → {path}")
                        ok += 1
                    except Exception as e:
                        print(f"  ❌  {item_type} / {brand} / {model.model} colors — {e}")
                        fail += 1

    print(f"\nГотово: {ok} создано, {fail} ошибок.")


def main():
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Генерация коллажей экипировки и байков")
    parser.add_argument(
        "--type",
        choices=["bike", "helmet", "jacket", "suit", "glove", "boot"],
        help="Тип каталога (по умолчанию — все)",
    )
    parser.add_argument("--brand", help="Фильтр по бренду (частичное совпадение)")
    parser.add_argument("--force", action="store_true", help="Пересоздать даже существующие (чистит кеш)")
    args = parser.parse_args()

    asyncio.run(run_collage_batch(args.type, args.brand, args.force))


if __name__ == "__main__":
    main()
