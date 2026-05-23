"""
Генерирует силуэты мотоциклов для каталога выбора байка.
Результат: media/bikes/<brand_slug>/<model_slug>/<model_slug>_silhouette.jpg

Запуск:
    python make_silhouettes.py --single media/bikes/honda/goldwing/goldwing_beige.jpg media/test.jpg
    python make_silhouettes.py                   # все байки из БД
    python make_silhouettes.py --brand Honda     # только Honda
    python make_silhouettes.py --force           # пересоздать существующие
"""

import argparse
import asyncio
import cv2
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


BG_COLOR   = (15, 25, 35)
FILL_COLOR = (232, 102, 10)

_rembg_session = None


def _get_session():
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session
        print("⏳ Загружаем модель isnet-general-use (первый запуск ~170 MB)...")
        _rembg_session = new_session("isnet-general-use", providers=["CUDAExecutionProvider"])  # CUDAExecutionProvider / CPUExecutionProvider
        print("✅ Модель загружена.")
    return _rembg_session


# Основная функция
def make_silhouette(
    input_path: str | Path,
    output_path: str | Path,
    card_size: tuple[int, int] = (1000, 1000),
) -> Path:
    """
    Убирает фон через rembg (нейросеть), заливает силуэт FILL_COLOR,
    помещает на карточку BG_COLOR и сохраняет в output_path.
    """
    from rembg import remove

    input_path  = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Файл не найден: {input_path.resolve()}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"  🔍 Обрабатываем: {input_path.name}")

    with open(input_path, "rb") as f:
        raw = f.read()

    result_bytes = remove(raw, session=_get_session())
    img = Image.open(BytesIO(result_bytes)).convert("RGBA")

    alpha = img.split()[3]
    alpha_smooth = alpha.filter(ImageFilter.GaussianBlur(radius=1.4))
    alpha_arr = np.array(alpha_smooth)

    _, binary = cv2.threshold(alpha_arr, 20, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(binary)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    h, w = filled.shape

    rows, cols = np.where(filled > 0)
    if len(rows) > 0:
        top_y = rows.min()
        band_threshold = top_y + int((rows.max() - top_y) * 0.10)
        top_mask = rows <= band_threshold
        top_x = cols[top_mask].mean()
        if top_x <= w / 2:
            filled = np.fliplr(filled)

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    mask = filled > 0
    rgba[mask] = (*FILL_COLOR, 255)
    rgba[~mask] = (0, 0, 0, 0)

    sil = Image.fromarray(rgba, "RGBA")

    pad = 30
    sil.thumbnail(
        (card_size[0] - pad * 2, card_size[1] - pad * 2),
        Image.LANCZOS,
    )

    canvas = Image.new("RGB", card_size, BG_COLOR)
    x = (card_size[0] - sil.width)  // 2
    y = (card_size[1] - sil.height) // 2
    canvas.paste(sil, (x, y), sil)
    canvas.save(output_path, "JPEG", quality=95)

    return output_path.resolve()


# Путь к силуэту модели
def silhouette_path_for_model(src_file: Path) -> Path:
    return src_file.parent / f"{src_file.stem}_silhouette.jpg"


# Batch из БД
async def run_batch(brand_filter: str | None, force: bool, media_dir: Path):
    sys.path.insert(0, str(Path(__file__).parent))
    import database as db
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from models import Bike

    async with db.get_session() as session:
        q = select(Bike).options(selectinload(Bike.files))
        if brand_filter:
            q = q.where(Bike.brand.ilike(f"%{brand_filter}%"))
        result = await session.execute(q)
        bikes = result.scalars().all()

    if not bikes:
        print("Байки не найдены.")
        return

    _get_session()

    ok = skip = fail = 0

    for bike in bikes:
        if not bike.files:
            print(f"  ⚠  {bike.brand} {bike.model} — нет файлов, пропускаем")
            skip += 1
            continue

        src_relative = bike.files[0].file
        src = media_dir / src_relative
        model_folder = src.parent
        dst = model_folder / f"{model_folder.name}_silhouette.jpg"

        if dst.exists() and not force:
            print(f"  ⏭  {bike.brand} {bike.model} — уже существует, пропускаем")
            skip += 1
            continue

        try:
            path = make_silhouette(src, dst)
            print(f"  ✅  {bike.brand} {bike.model} → {path}")
            ok += 1
        except FileNotFoundError as e:
            print(f"  ❌  {bike.brand} {bike.model} — {e}")
            fail += 1
        except Exception as e:
            print(f"  ❌  {bike.brand} {bike.model} — неожиданная ошибка: {e}")
            fail += 1

    print(f"\nГотово: {ok} создано, {skip} пропущено, {fail} ошибок.")


def main():
    parser = argparse.ArgumentParser(description="Генерация силуэтов байков через rembg GPU")
    parser.add_argument("--brand",  help="Фильтр по бренду (частичное совпадение)")
    parser.add_argument("--force",  action="store_true", help="Пересоздать даже существующие")
    parser.add_argument("--media",  default="media", help="Путь к media/ (по умолчанию: media)")
    parser.add_argument(
        "--single",
        metavar="INPUT",
        help="Один файл: --single path/to/bike.jpg",
    )
    args = parser.parse_args()

    if args.single:
        inp = Path(args.single)
        dst = inp.parent / f"{inp.parent.name}_silhouette.jpg"
        path = make_silhouette(inp, dst)
        print(f"✅ Сохранено: {path}")
    else:
        media_dir = Path(args.media).resolve()
        asyncio.run(run_batch(args.brand, args.force, media_dir))


if __name__ == "__main__":
    main()
