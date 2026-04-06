import random
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from random import choice
from config import settings
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from models import (
    Account, Generation, Location, DictionaryPrompt, Collage,
    User, UserPhotoset,
    Bike, BikeColor, BikeFile,
    Helmet, HelmetColor, HelmetFile,
    Jacket, JacketColor, JacketFile,
    Glove, GloveColor, GloveFile,
)


# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

_USER_OPTIONS = [
    selectinload(User.bike_file).selectinload(BikeFile.bike).selectinload(Bike.location),
    selectinload(User.bike_file).selectinload(BikeFile.color),
    selectinload(User.helmet_file).selectinload(HelmetFile.helmet),
    selectinload(User.helmet_file).selectinload(HelmetFile.color),
    selectinload(User.jacket_file).selectinload(JacketFile.jacket),
    selectinload(User.jacket_file).selectinload(JacketFile.color),
    selectinload(User.glove_file).selectinload(GloveFile.glove),
    selectinload(User.glove_file).selectinload(GloveFile.color),
    selectinload(User.photoset),
]


async def get_user_by_tg_id(tg_id: int) -> User | None:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.tg_id == tg_id).options(*_USER_OPTIONS)
        )
        return result.scalar_one_or_none()


async def get_or_create_user(tg_id: int, name: str | None = None) -> tuple[User, bool]:
    """Возвращает (user, created). Если юзер уже есть — просто отдаёт его."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.tg_id == tg_id).options(*_USER_OPTIONS)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            return user, False

        user = User(tg_id=tg_id, name=name)
        session.add(user)
        await session.flush()
        return user, True


async def update_user_profile(
    tg_id: int,
    name: str | None = None,
    phone: str | None = None,
    city: str | None = None,
) -> None:
    values: dict = {}
    if name is not None:
        values["name"] = name
    if phone is not None:
        values["phone"] = phone
    if city is not None:
        values["city"] = city
    if not values:
        return
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(**values)
        )


async def update_user_bike_file(tg_id: int, bike_file_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(bike_file_id=bike_file_id)
        )


async def update_user_helmet_file(tg_id: int, helmet_file_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(helmet_file_id=helmet_file_id)
        )


async def increment_spent_stars(tg_id: int, amount: int = 1) -> None:
    async with get_session() as session:
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(spent_stars=User.spent_stars + amount)
        )


# ---------------------------------------------------------------------------
# UserPhotoset
# ---------------------------------------------------------------------------

async def upsert_user_photoset(
    user_id: int,
    front_photo: str | None = None,
    side_photo: str | None = None,
    body_photo: str | None = None,
) -> UserPhotoset:
    """Создаёт фотосет если нет, или обновляет только переданные поля."""
    async with get_session() as session:
        result = await session.execute(
            select(UserPhotoset).where(UserPhotoset.user_id == user_id)
        )
        photoset = result.scalar_one_or_none()

        if photoset is None:
            photoset = UserPhotoset(
                user_id=user_id,
                front_photo=front_photo,
                side_photo=side_photo,
                body_photo=body_photo,
            )
            session.add(photoset)
        else:
            if front_photo is not None:
                photoset.front_photo = front_photo
            if side_photo is not None:
                photoset.side_photo = side_photo
            if body_photo is not None:
                photoset.body_photo = body_photo

        await session.flush()
        return photoset


def photoset_is_complete(photoset: UserPhotoset | None) -> bool:
    """Все три фото загружены."""
    return (
        photoset is not None
        and photoset.front_photo is not None
        and photoset.side_photo is not None
        and photoset.body_photo is not None
    )


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

async def get_all_locations() -> list[Location]:
    async with get_session() as session:
        result = await session.execute(select(Location).order_by(Location.name))
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Bike
# ---------------------------------------------------------------------------

async def get_bike_brands() -> list[str]:
    async with get_session() as session:
        result = await session.execute(
            select(Bike.brand).distinct().order_by(Bike.brand)
        )
        return list(result.scalars().all())


async def get_bike_models(brand: str) -> list[Bike]:
    async with get_session() as session:
        result = await session.execute(
            select(Bike).where(Bike.brand == brand).order_by(Bike.model)
        )
        return list(result.scalars().all())


async def get_bike_colors(bike_id: int) -> list[BikeColor]:
    """Универсальные цвета (bike_id IS NULL) + специфичные для конкретного байка."""
    async with get_session() as session:
        result = await session.execute(
            select(BikeColor)
            .where((BikeColor.bike_id == bike_id) | (BikeColor.bike_id.is_(None)))
            .order_by(BikeColor.name)
        )
        return list(result.scalars().all())


async def get_bike_file(bike_id: int, color_id: int) -> BikeFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(BikeFile)
            .where(BikeFile.bike_id == bike_id, BikeFile.color_id == color_id)
            .options(
                selectinload(BikeFile.bike).selectinload(Bike.location),
                selectinload(BikeFile.color),
            )
        )
        return result.scalar_one_or_none()


async def get_bike_file_by_id(bike_file_id: int) -> BikeFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(BikeFile)
            .where(BikeFile.id == bike_file_id)
            .options(
                selectinload(BikeFile.bike).selectinload(Bike.location),
                selectinload(BikeFile.color),
            )
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Helmet
# ---------------------------------------------------------------------------

async def get_helmet_brands() -> list[str]:
    async with get_session() as session:
        result = await session.execute(
            select(Helmet.brand).distinct().order_by(Helmet.brand)
        )
        return list(result.scalars().all())


async def get_helmet_models(brand: str) -> list[Helmet]:
    async with get_session() as session:
        result = await session.execute(
            select(Helmet).where(Helmet.brand == brand).order_by(Helmet.model)
        )
        return list(result.scalars().all())


async def get_helmet_colors(helmet_id: int) -> list[HelmetColor]:
    async with get_session() as session:
        result = await session.execute(
            select(HelmetColor)
            .where(
                (HelmetColor.helmet_id == helmet_id) | (HelmetColor.helmet_id.is_(None))
            )
            .order_by(HelmetColor.name)
        )
        return list(result.scalars().all())


async def get_helmet_file(helmet_id: int, color_id: int) -> HelmetFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(HelmetFile)
            .where(HelmetFile.helmet_id == helmet_id, HelmetFile.color_id == color_id)
            .options(
                selectinload(HelmetFile.helmet),
                selectinload(HelmetFile.color),
            )
        )
        return result.scalar_one_or_none()


async def get_helmet_file_by_id(helmet_file_id: int) -> HelmetFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(HelmetFile)
            .where(HelmetFile.id == helmet_file_id)
            .options(
                selectinload(HelmetFile.helmet),
                selectinload(HelmetFile.color),
            )
        )
        return result.scalar_one_or_none()


async def clear_user_helmet_file(tg_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(helmet_file_id=None)
        )


# ---------------------------------------------------------------------------
# Jacket
# ---------------------------------------------------------------------------

async def get_jacket_brands() -> list[str]:
    async with get_session() as session:
        result = await session.execute(
            select(Jacket.brand).distinct().order_by(Jacket.brand)
        )
        return list(result.scalars().all())


async def get_jacket_models(brand: str) -> list[Jacket]:
    async with get_session() as session:
        result = await session.execute(
            select(Jacket).where(Jacket.brand == brand).order_by(Jacket.model)
        )
        return list(result.scalars().all())


async def get_jacket_colors(jacket_id: int) -> list[JacketColor]:
    async with get_session() as session:
        result = await session.execute(
            select(JacketColor)
            .where(
                (JacketColor.jacket_id == jacket_id) | (JacketColor.jacket_id.is_(None))
            )
            .order_by(JacketColor.name)
        )
        return list(result.scalars().all())


async def get_jacket_file(jacket_id: int, color_id: int) -> JacketFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(JacketFile)
            .where(JacketFile.jacket_id == jacket_id, JacketFile.color_id == color_id)
            .options(
                selectinload(JacketFile.jacket),
                selectinload(JacketFile.color),
            )
        )
        return result.scalar_one_or_none()


async def get_jacket_file_by_id(jacket_file_id: int) -> JacketFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(JacketFile)
            .where(JacketFile.id == jacket_file_id)
            .options(
                selectinload(JacketFile.jacket),
                selectinload(JacketFile.color),
            )
        )
        return result.scalar_one_or_none()


async def update_user_jacket_file(tg_id: int, jacket_file_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(jacket_file_id=jacket_file_id)
        )


async def clear_user_jacket_file(tg_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(jacket_file_id=None)
        )


# ---------------------------------------------------------------------------
# Glove
# ---------------------------------------------------------------------------

async def get_glove_brands() -> list[str]:
    async with get_session() as session:
        result = await session.execute(
            select(Glove.brand).distinct().order_by(Glove.brand)
        )
        return list(result.scalars().all())


async def get_glove_models(brand: str) -> list[Glove]:
    async with get_session() as session:
        result = await session.execute(
            select(Glove).where(Glove.brand == brand).order_by(Glove.model)
        )
        return list(result.scalars().all())


async def get_glove_colors(glove_id: int) -> list[GloveColor]:
    async with get_session() as session:
        result = await session.execute(
            select(GloveColor)
            .where(
                (GloveColor.glove_id == glove_id) | (GloveColor.glove_id.is_(None))
            )
            .order_by(GloveColor.name)
        )
        return list(result.scalars().all())


async def get_glove_file(glove_id: int, color_id: int) -> GloveFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(GloveFile)
            .where(GloveFile.glove_id == glove_id, GloveFile.color_id == color_id)
            .options(
                selectinload(GloveFile.glove),
                selectinload(GloveFile.color),
            )
        )
        return result.scalar_one_or_none()


async def get_glove_file_by_id(glove_file_id: int) -> GloveFile | None:
    async with get_session() as session:
        result = await session.execute(
            select(GloveFile)
            .where(GloveFile.id == glove_file_id)
            .options(
                selectinload(GloveFile.glove),
                selectinload(GloveFile.color),
            )
        )
        return result.scalar_one_or_none()


async def update_user_glove_file(tg_id: int, glove_file_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(glove_file_id=glove_file_id)
        )


async def clear_user_glove_file(tg_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(User).where(User.tg_id == tg_id).values(glove_file_id=None)
        )


# ---------------------------------------------------------------------------
# Account (ротация токенов Gemini)
# ---------------------------------------------------------------------------

async def get_active_account() -> Account | None:
    """Случайный активный аккаунт — равномерная нагрузка на токены."""
    async with get_session() as session:
        result = await session.execute(
            select(Account).where(Account.is_active == True)  # noqa: E712
        )
        accounts = list(result.scalars().all())
        return choice(accounts) if accounts else None


async def deactivate_account(account_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            update(Account).where(Account.id == account_id).values(is_active=False)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def create_generation(
    user_id: int,
    account_id: int,
    bike_file: BikeFile,
    helmet_file_id: int | None = None,
    jacket_file_id: int | None = None,
) -> Generation:
    async with get_session() as session:
        generation = Generation(
            user_id=user_id,
            account_id=account_id,
            bike_file_id=bike_file.id,
            helmet_file_id=helmet_file_id,
            jacket_file_id=jacket_file_id,
            status="pending",
        )
        session.add(generation)
        await session.flush()
        return generation

async def update_generation_status(generation_id: int, status: str) -> None:
    """status: 'success' | 'failed'"""
    async with get_session() as session:
        await session.execute(
            update(Generation)
            .where(Generation.id == generation_id)
            .values(status=status, updated_date=func.now())
        )


async def get_user_generations(user_id: int, limit: int = 10) -> list[Generation]:
    async with get_session() as session:
        result = await session.execute(
            select(Generation)
            .where(Generation.user_id == user_id)
            .order_by(Generation.created_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# DictionaryPrompt
# ---------------------------------------------------------------------------

async def get_prompts_by_type(type: str) -> list[DictionaryPrompt]:
    async with get_session() as session:
        result = await session.execute(
            select(DictionaryPrompt).where(DictionaryPrompt.type == type)
        )
        return list(result.scalars().all())


async def get_default_prompt() -> DictionaryPrompt | None:
    """Главный промпт с {helmet}, {location}, {jacket}."""
    async with get_session() as session:
        result = await session.execute(
            select(DictionaryPrompt)
            .where(DictionaryPrompt.type == "default")
            .limit(1)
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Collage
# ---------------------------------------------------------------------------

async def get_collage_state(type: str, brand: str):
    """
    Один запрос: текущее кол-во моделей + закэшированные данные.
    Возвращает (current_count, cached_file | None, cached_count | None)
    """
    model_map = {"helmet": Helmet, "jacket": Jacket, "glove": Glove}
    Model = model_map[type]

    async with get_session() as session:
        result = await session.execute(
            select(
                func.count(Model.id).label("current_count"),
                Collage.file,
                Collage.models_count,
            )
            .where(Model.brand == brand)
            .outerjoin(
                Collage,
                (Collage.type == type) & (Collage.brand == brand)
            )
            .group_by(Collage.file, Collage.models_count)
        )
        return result.one()


async def upsert_collage(type: str, brand: str, file_path: str, count: int) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(Collage).where(Collage.type == type, Collage.brand == brand)
        )
        cached = result.scalar_one_or_none()
        if cached:
            cached.file = file_path
            cached.models_count = count
        else:
            session.add(Collage(type=type, brand=brand, file=file_path, models_count=count))


async def get_items_for_collage(item_type: str, brand: str) -> list[tuple[str, str | None]]:
    """Возвращает (model, first_file_path) для построения коллажа."""
    model_map = {
        "helmet": (Helmet, HelmetFile, Helmet.model),
        "jacket": (Jacket, JacketFile, Jacket.model),
        "glove": (Glove, GloveFile, Glove.model),
    }
    Model, FileModel, order_col = model_map[item_type]
    random_color = item_type != "helmet"

    async with get_session() as session:
        result = await session.execute(
            select(Model).where(Model.brand == brand)
            .options(selectinload(Model.files))
            .order_by(order_col)
        )
        rows = result.scalars().all()

        def pick_file(files):
            if not files:
                return None
            return random.choice(files).file if random_color else files[0].file

        return [(r.model, pick_file(r.files)) for r in rows]
