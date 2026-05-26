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


BASE_DIR = Path(__file__).resolve().parent / "media"


# ============================================================================
# ДИЗАЙН
# ============================================================================

# Палитра — Telegram dark theme
PAGE_BG = (23, 33, 43)              # #17212B — фон чата TG
CARD_BG = (36, 48, 62)              # #24303E — карточка чуть светлее фона
CARD_BORDER = (52, 66, 82)
TEXT_PRIMARY = (245, 248, 250)
TEXT_SECONDARY = (130, 145, 160)
TEXT_ACCENT = (232, 102, 10)        # оранжевый акцент

# Цвет фона силуэтов байков (нужен для корректного crop)
BIKE_RAW_BG = (15, 25, 35)

# Размеры карточек
CARD_SIZE = 400
GAP = 16
PADDING = 36
PLATE_H = 84
ACCENT_BAR_W = 4
CORNER_RADIUS = 14

# Размеры хедера
HEADER_PADDING_TOP = 50
HEADER_PADDING_BOTTOM = 36
HEADER_GAP_LABEL_TITLE = 10
HEADER_GAP_TITLE_SUBTITLE = 14


# ============================================================================
# МАППИНГИ
# ============================================================================

TYPE_SUBDIR = {
    "bike":    "bikes",
    "helmet":  "helmets",
    "jacket":  "jackets",
    "suit":    "suits",
    "glove":   "gloves",
    "boot":    "boots",
}

TYPE_LABEL = {
    "bike":   "ВЫБОР МОТОЦИКЛА",
    "helmet": "ВЫБОР ШЛЕМА",
    "jacket": "ВЫБОР КУРТКИ",
    "suit":   "ВЫБОР КОМБИНЕЗОНА",
    "glove":  "ВЫБОР ПЕРЧАТОК",
    "boot":   "ВЫБОР БОТИНОК",
}

TYPE_TITLE_PLURAL = {
    "bike":   "Мотоциклы",
    "helmet": "Шлемы",
    "jacket": "Куртки",
    "suit":   "Комбинезоны",
    "glove":  "Перчатки",
    "boot":   "Ботинки",
}

MODEL_FORMS = ("модель", "модели", "моделей")
COLOR_FORMS = ("цвет", "цвета", "цветов")


# ============================================================================
# ШРИФТЫ
# ============================================================================

def _load_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


font_header_label    = _load_font(20, bold=True)
font_header_title    = _load_font(48, bold=True)
font_header_subtitle = _load_font(20, bold=False)
font_brand           = _load_font(14, bold=True)
font_model           = _load_font(24, bold=True)


# ============================================================================
# ХЕЛПЕРЫ
# ============================================================================

def _brand_dir(item_type: str, brand: str) -> Path:
    slug = brand.lower().replace(" ", "_")
    path = BASE_DIR / "collages" / TYPE_SUBDIR[item_type] / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _plural_ru(n: int, forms: tuple[str, str, str]) -> str:
    """Возвращает правильную форму существительного: 1 модель / 2 модели / 5 моделей."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return forms[1]
    return forms[2]


def load_image(path: str) -> Image.Image:
    if not path:
        raise ValueError("Empty image path")
    if path.startswith("http"):
        headers = {"User-Agent": "Mozilla/5.0 CollageGenerator/1.0"}
        resp = requests.get(path, timeout=10, headers=headers)
        with Image.open(BytesIO(resp.content)) as img:
            img.load()
            return img.copy()
    full_path = BASE_DIR / Path(path)
    if not full_path.exists():
        raise FileNotFoundError(f"Not found: {full_path}")
    with Image.open(full_path) as img:
        img.load()
        return img.copy()


def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while draw.textlength(text + "...", font=font) > max_w and len(text) > 1:
        text = text[:-1]
    return text.rstrip() + "..."


def _crop_to_content(img: Image.Image, bg_color=BIKE_RAW_BG, margin: int = 20) -> Image.Image:
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


def _bike_silhouette_to_rgba(img: Image.Image, bg_color=BIKE_RAW_BG, threshold: int = 10) -> Image.Image:
    """Делает фон силуэта байка прозрачным, чтобы он лёг на CARD_BG без видимой 'рамки'."""
    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, bg_color)
    diff = ImageChops.difference(rgb, bg).convert("L")
    mask = diff.point(lambda p: 255 if p > threshold else 0)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(mask)
    return rgba


def _fit_on(img: Image.Image, w: int, h: int, bg: tuple, crop: bool = False) -> Image.Image:
    if crop:
        img = _crop_to_content(img)
        img = _bike_silhouette_to_rgba(img)  # bg → прозрачный, чтобы слиться с CARD_BG
    ratio = min(w / img.width, h / img.height) * 0.85
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (w, h), bg)
    x, y = (w - nw) // 2, (h - nh) // 2

    if img.mode == "RGBA":
        canvas.paste(img, (x, y), img)
    else:
        canvas.paste(img, (x, y))
    return canvas


# ============================================================================
# КАРТОЧКА
# ============================================================================

def _draw_card(label_top: str, label_bottom: str, photo_path: str | None, dark_bg: bool = False) -> Image.Image:
    """Карточка: фото вверху + тёмная плашка с вертикальным акцентом и текстом снизу.
    dark_bg=True — для байков (силуэты на тёмном фоне);
    dark_bg=False — для экипа (фото на белом фоне)."""
    card = Image.new("RGBA", (CARD_SIZE, CARD_SIZE), (0, 0, 0, 0))

    photo_h = CARD_SIZE - PLATE_H
    photo_bg = CARD_BG if dark_bg else (255, 255, 255)

    photo_canvas = Image.new("RGB", (CARD_SIZE, photo_h), photo_bg)
    if photo_path:
        try:
            photo = load_image(photo_path).convert("RGBA")
            fitted = _fit_on(photo, CARD_SIZE, photo_h, photo_bg, crop=dark_bg)
            photo_canvas.paste(fitted, (0, 0))
        except Exception as e:
            print(f"Error loading image: {e}")
    card.paste(photo_canvas, (0, 0))

    # Плашка с текстом снизу
    plate = Image.new("RGB", (CARD_SIZE, PLATE_H), CARD_BG)
    pd = ImageDraw.Draw(plate)

    # Вертикальный акцент-бар слева
    pd.rectangle([(0, 0), (ACCENT_BAR_W, PLATE_H)], fill=TEXT_ACCENT)

    text_x = ACCENT_BAR_W + 16
    text_w_limit = CARD_SIZE - text_x - 16

    brand_txt = _truncate(pd, label_top.upper(), font_brand, text_w_limit)
    pd.text((text_x, 14), brand_txt, font=font_brand, fill=TEXT_ACCENT)

    model_txt = _truncate(pd, label_bottom, font_model, text_w_limit)
    pd.text((text_x, 36), model_txt, font=font_model, fill=TEXT_PRIMARY)

    card.paste(plate, (0, photo_h))

    # Закругление углов через supersampling (4x → LANCZOS) — гладкие края без зубчиков
    SS = 4
    big_size = CARD_SIZE * SS
    big_radius = CORNER_RADIUS * SS

    big_mask = Image.new("L", (big_size, big_size), 0)
    ImageDraw.Draw(big_mask).rounded_rectangle((0, 0, big_size, big_size), big_radius, fill=255)
    mask = big_mask.resize((CARD_SIZE, CARD_SIZE), Image.LANCZOS)

    rounded = Image.new("RGBA", (CARD_SIZE, CARD_SIZE), (0, 0, 0, 0))
    rounded.paste(card, (0, 0), mask=mask)

    # Бордюр — тоже через supersampling, чтобы тонкая линия по дуге не "ступенчилась"
    big_border = Image.new("RGBA", (big_size, big_size), (0, 0, 0, 0))
    ImageDraw.Draw(big_border).rounded_rectangle(
        (0, 0, big_size - 1, big_size - 1),
        big_radius,
        outline=CARD_BORDER,
        width=SS,  # 1px в финальном = SS px в supersampled
    )
    border = big_border.resize((CARD_SIZE, CARD_SIZE), Image.LANCZOS)
    rounded.alpha_composite(border)

    return rounded


# ============================================================================
# ХЕДЕР
# ============================================================================

def _measure_header_h() -> int:
    """Оценка высоты хедера на основе метрик шрифтов."""
    dummy = Image.new("RGB", (1, 1))
    d = ImageDraw.Draw(dummy)
    h_label = d.textbbox((0, 0), "X", font=font_header_label)[3]
    h_title = d.textbbox((0, 0), "X", font=font_header_title)[3]
    h_subtitle = d.textbbox((0, 0), "X", font=font_header_subtitle)[3]
    return (
        HEADER_PADDING_TOP + h_label
        + HEADER_GAP_LABEL_TITLE + h_title
        + HEADER_GAP_TITLE_SUBTITLE + h_subtitle
        + HEADER_PADDING_BOTTOM
    )


def _draw_header(canvas: Image.Image, label: str, title: str, subtitle: str) -> None:
    draw = ImageDraw.Draw(canvas)
    x = PADDING
    y = HEADER_PADDING_TOP

    draw.text((x, y), label, font=font_header_label, fill=TEXT_ACCENT)
    y = draw.textbbox((x, y), label, font=font_header_label)[3] + HEADER_GAP_LABEL_TITLE

    draw.text((x, y), title, font=font_header_title, fill=TEXT_PRIMARY)
    y = draw.textbbox((x, y), title, font=font_header_title)[3] + HEADER_GAP_TITLE_SUBTITLE

    draw.text((x, y), subtitle, font=font_header_subtitle, fill=TEXT_SECONDARY)


# ============================================================================
# СБОРКА КОЛЛАЖА
# ============================================================================

class ItemView(NamedTuple):
    label_top: str
    label_bottom: str
    photo_path: str | None


def _build_collage(
    items: list[ItemView],
    out_path: Path,
    header_label: str,
    header_title: str,
    header_subtitle: str,
    dark_bg: bool = False,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cols = 4 if len(items) > 9 else 3
    rows = -(-len(items) // cols)

    grid_w = cols * CARD_SIZE + (cols - 1) * GAP
    grid_h = rows * CARD_SIZE + (rows - 1) * GAP

    w = grid_w + PADDING * 2
    header_h = _measure_header_h()
    h = header_h + grid_h + PADDING

    canvas = Image.new("RGB", (w, h), PAGE_BG)
    _draw_header(canvas, header_label, header_title, header_subtitle)

    for idx, item in enumerate(items):
        col, row = idx % cols, idx // cols
        x = PADDING + col * (CARD_SIZE + GAP)
        y = header_h + row * (CARD_SIZE + GAP)
        card_img = _draw_card(item.label_top, item.label_bottom, item.photo_path, dark_bg=dark_bg)
        canvas.paste(card_img, (x, y), card_img)

    canvas.save(out_path, "JPEG", quality=95, optimize=True)
    return out_path


# ============================================================================
# ПУБЛИЧНОЕ API
# ============================================================================

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

    n = len(items)
    header_label = TYPE_LABEL[item_type]
    header_title = f"{TYPE_TITLE_PLURAL[item_type]} {brand}"
    header_subtitle = f"{n} {_plural_ru(n, MODEL_FORMS)}"

    def _generate():
        return _build_collage(items, out_path, header_label, header_title, header_subtitle, dark_bg=dark_bg)

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

    n = len(items)
    header_label = "ВЫБОР ЦВЕТА"
    header_title = f"{brand} {model_name}"
    header_subtitle = f"{n} {_plural_ru(n, COLOR_FORMS)}"

    def _generate():
        return _build_collage(items, out_path, header_label, header_title, header_subtitle)

    path = await asyncio.get_running_loop().run_in_executor(None, _generate)
    await db.upsert_color_collage(item_type, brand, model_id, str(path), current_count)
    return path


# ============================================================================
# РУЧНОЙ ЗАПУСК
# ============================================================================

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

            if item_type != "bike":
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
    import sys

    # На Windows консоль может быть cp1251 — переключаем stdout в UTF-8,
    # чтобы эмодзи и кириллица печатались корректно.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

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
