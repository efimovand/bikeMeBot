from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ---------------------------------------------------------------------------
# Callback data
# ---------------------------------------------------------------------------

class PolicyCallback(CallbackData, prefix="policy"):
    action: str  # agree


class MenuCallback(CallbackData, prefix="menu"):
    action: str  # bike / helmet / photos / generate


# Bike
class BikeBrandCallback(CallbackData, prefix="bike_brand"):
    brand: str


class BikeModelCallback(CallbackData, prefix="bike_model"):
    bike_id: int


class BikeColorCallback(CallbackData, prefix="bike_color"):
    bike_id: int
    color_id: int


# Helmet
class HelmetBrandCallback(CallbackData, prefix="helmet_brand"):
    brand: str


class HelmetModelCallback(CallbackData, prefix="helmet_model"):
    helmet_id: int


class HelmetColorCallback(CallbackData, prefix="helmet_color"):
    helmet_id: int
    color_id: int


# Jacket
class JacketBrandCallback(CallbackData, prefix="jacket_brand"):
    brand: str


class JacketModelCallback(CallbackData, prefix="jacket_model"):
    jacket_id: int


class JacketColorCallback(CallbackData, prefix="jacket_color"):
    jacket_id: int
    color_id: int


# Suit
class SuitBrandCallback(CallbackData, prefix="suit_brand"):
    brand: str


class SuitModelCallback(CallbackData, prefix="suit_model"):
    suit_id: int


class SuitColorCallback(CallbackData, prefix="suit_color"):
    suit_id: int
    color_id: int


# Glove
class GloveBrandCallback(CallbackData, prefix="glove_brand"):
    brand: str


class GloveModelCallback(CallbackData, prefix="glove_model"):
    glove_id: int


class GloveColorCallback(CallbackData, prefix="glove_color"):
    glove_id: int
    color_id: int


# Boot
class BootBrandCallback(CallbackData, prefix="boot_brand"):
    brand: str


class BootModelCallback(CallbackData, prefix="boot_model"):
    boot_id: int


class BootColorCallback(CallbackData, prefix="boot_color"):
    boot_id: int
    color_id: int


class OnboardingContinueCallback(CallbackData, prefix="onb_cont"):
    action: str  # "helmet" | "jacket" | "photos"


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def policy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Согласен с политикой",
        callback_data=PolicyCallback(action="agree")
    )
    return builder.as_markup()


def main_menu_keyboard(
    has_bike: bool,
    has_helmet: bool,
    has_jacket: bool,
    has_suit: bool,
    has_glove: bool,
    has_boot: bool,
    has_photos: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🏍 Изменить мотоцикл" if has_bike else "🏍 Выбрать мотоцикл",
        callback_data=MenuCallback(action="bike")
    )

    if has_helmet:
        builder.button(text="🪖 Изменить шлем", callback_data=MenuCallback(action="helmet"))
        builder.button(text="❌ Убрать шлем", callback_data=MenuCallback(action="helmet_remove"))
    else:
        builder.button(text="🪖 Выбрать шлем", callback_data=MenuCallback(action="helmet"))

    if has_jacket:
        builder.button(text="🧥 Изменить куртку", callback_data=MenuCallback(action="jacket"))
        builder.button(text="❌ Убрать куртку", callback_data=MenuCallback(action="jacket_remove"))
    else:
        builder.button(text="🧥 Выбрать куртку", callback_data=MenuCallback(action="jacket"))

    if has_suit:
        builder.button(text="🏁 Изменить комбинезон", callback_data=MenuCallback(action="suit"))
        builder.button(text="❌ Убрать комбинезон", callback_data=MenuCallback(action="suit_remove"))
    else:
        builder.button(text="🏁 Выбрать комбинезон", callback_data=MenuCallback(action="suit"))

    if has_glove:
        builder.button(text="🧤 Изменить перчатки", callback_data=MenuCallback(action="glove"))
        builder.button(text="❌ Убрать перчатки", callback_data=MenuCallback(action="glove_remove"))
    else:
        builder.button(text="🧤 Выбрать перчатки", callback_data=MenuCallback(action="glove"))

    if has_boot:
        builder.button(text="🥾 Изменить ботинки", callback_data=MenuCallback(action="boot"))
        builder.button(text="❌ Убрать ботинки", callback_data=MenuCallback(action="boot_remove"))
    else:
        builder.button(text="🥾 Выбрать ботинки", callback_data=MenuCallback(action="boot"))

    builder.button(
        text="📷 Изменить фото" if has_photos else "📷 Загрузить фото",
        callback_data=MenuCallback(action="photos")
    )

    if has_bike and has_photos:
        builder.button(text="✨ Сгенерировать", callback_data=MenuCallback(action="generate"))

    builder.adjust(
        1,
        2 if has_helmet else 1,
        2 if has_jacket else 1,
        2 if has_suit else 1,
        2 if has_glove else 1,
        2 if has_boot else 1,
        1,
        1,
    )
    return builder.as_markup()


def after_bike_onboarding_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🪖 Добавить шлем",
        callback_data=OnboardingContinueCallback(action="helmet")
    )
    builder.button(
        text="🧥 Добавить куртку",
        callback_data=OnboardingContinueCallback(action="jacket")
    )
    builder.button(
        text="➡️ Продолжить",
        callback_data=OnboardingContinueCallback(action="photos")
    )
    builder.adjust(1)
    return builder.as_markup()


def brands_keyboard(brands: list[str], callback_class) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for brand in brands:
        builder.button(text=brand, callback_data=callback_class(brand=brand))
    builder.adjust(2)
    return builder.as_markup()


def bike_models_keyboard(bikes: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for bike in bikes:
        builder.button(
            text=bike.model,
            callback_data=BikeModelCallback(bike_id=bike.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def bike_colors_keyboard(colors: list, bike_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for color in colors:
        builder.button(
            text=color.name,
            callback_data=BikeColorCallback(bike_id=bike_id, color_id=color.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def helmet_models_keyboard(helmets: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for helmet in helmets:
        builder.button(
            text=helmet.model,
            callback_data=HelmetModelCallback(helmet_id=helmet.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def helmet_colors_keyboard(colors: list, helmet_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for color in colors:
        builder.button(
            text=color.name,
            callback_data=HelmetColorCallback(helmet_id=helmet_id, color_id=color.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def jacket_models_keyboard(jackets: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for jacket in jackets:
        builder.button(
            text=jacket.model,
            callback_data=JacketModelCallback(jacket_id=jacket.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def jacket_colors_keyboard(colors: list, jacket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for color in colors:
        builder.button(
            text=color.name,
            callback_data=JacketColorCallback(jacket_id=jacket_id, color_id=color.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def suit_models_keyboard(suits: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for suit in suits:
        builder.button(text=suit.model, callback_data=SuitModelCallback(suit_id=suit.id))
    builder.adjust(1)
    return builder.as_markup()


def suit_colors_keyboard(colors: list, suit_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for color in colors:
        builder.button(
            text=color.name,
            callback_data=SuitColorCallback(suit_id=suit_id, color_id=color.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def glove_models_keyboard(gloves: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for glove in gloves:
        builder.button(text=glove.model, callback_data=GloveModelCallback(glove_id=glove.id))
    builder.adjust(1)
    return builder.as_markup()


def glove_colors_keyboard(colors: list, glove_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for color in colors:
        builder.button(
            text=color.name,
            callback_data=GloveColorCallback(glove_id=glove_id, color_id=color.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def boot_models_keyboard(boots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for boot in boots:
        builder.button(text=boot.model, callback_data=BootModelCallback(boot_id=boot.id))
    builder.adjust(1)
    return builder.as_markup()


def boot_colors_keyboard(colors: list, boot_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for color in colors:
        builder.button(
            text=color.name,
            callback_data=BootColorCallback(boot_id=boot_id, color_id=color.id)
        )
    builder.adjust(1)
    return builder.as_markup()


def generate_again_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✨ Сгенерировать ещё раз",
        callback_data=MenuCallback(action="main_menu")
    )
    return builder.as_markup()
