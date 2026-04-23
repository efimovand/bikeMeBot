<div align="center">

```
██████╗ ██╗██╗  ██╗███████╗███╗   ███╗███████╗
██╔══██╗██║██║ ██╔╝██╔════╝████╗ ████║██╔════╝
██████╔╝██║█████╔╝ █████╗  ██╔████╔██║█████╗  
██╔══██╗██║██╔═██╗ ██╔══╝  ██║╚██╔╝██║██╔══╝  
██████╔╝██║██║  ██╗███████╗██║ ╚═╝ ██║███████╗
╚═════╝ ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚══════╝
```

**Примерь любой мотоцикл и экипировку — прямо на себя.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.26-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://aiogram.dev)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)](https://sqlalchemy.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## ✨ Что это такое

**BikeMe** — Telegram-бот, который с помощью генеративного ИИ создаёт фотореалистичные снимки: _ты_ на _своём_ мотоцикле, в _выбранной_ экипировке. Пользователь загружает три своих фото, выбирает байк и снаряжение — бот возвращает готовое изображение в высоком качестве.

```
Фото пользователя  +  Мотоцикл  +  Экипировка  →  🏍 Фотореалистичный результат
```

---

## 🎬 Как это работает

```
1. /start          → Онбординг + политика данных
2. Выбор байка     → Бренд → Модель → Цвет
3. Экипировка      → Шлем · Куртка · Комбинезон · Перчатки · Ботинки
4. Фото            → Анфас · Профиль · В полный рост
5. Генерация       → ИИ создаёт изображение (~80 сек)
6. Результат       → Фото прямо в чате 🎉
```

---

## 🗂 Структура проекта

```
bikeme/
│
├── bot.py                  # Точка входа, регистрация роутеров
├── config.py               # Настройки через pydantic-settings
├── models.py               # SQLAlchemy ORM-модели
├── database.py             # Все async-запросы к БД
├── keyboards.py            # Inline-клавиатуры и CallbackData
├── states.py               # FSM-состояния (aiogram)
├── prompts.py              # Сборка финального промпта для ИИ
├── kie_ai.py               # Клиент KIE AI: upload → task → poll → download
├── collage.py              # Генерация коллажей для выбора экипировки
├── utils.py                # Текст конфигурации пользователя
│
├── handlers/
│   ├── start.py            # Онбординг, главное меню
│   ├── bike.py             # Выбор мотоцикла
│   ├── helmet.py           # Выбор шлема
│   ├── jacket.py           # Выбор куртки
│   ├── suit.py             # Выбор комбинезона
│   ├── glove.py            # Выбор перчаток
│   ├── boot.py             # Выбор ботинок
│   ├── location.py         # Выбор локации
│   ├── photos.py           # Загрузка фото пользователя
│   ├── generate.py         # Запуск генерации + прогресс-бар
│   └── payment.py          # Оплата через Telegram Stars
│
├── alembic/                # Миграции БД
│   └── versions/
│
├── autogui/                # Автоматизация Google AI Studio (legacy)
│
└── media/                  # Медиафайлы
    ├── bikes/
    ├── helmets/
    ├── jackets/
    ├── suits/
    ├── gloves/
    ├── boots/
    ├── examples/
    │   ├── photoset/       # Примеры фото для онбординга
    │   └── results/        # Примеры генераций (1-9.jpg)
    ├── collages/           # Авто-генерируемые коллажи
    └── users/              # Фото и результаты пользователей
```

---

## 🛠 Стек технологий

| Слой | Технология |
|---|---|
| Бот | [aiogram 3](https://aiogram.dev) + asyncio |
| База данных | PostgreSQL + [SQLAlchemy 2.0](https://sqlalchemy.org) (async) |
| Миграции | [Alembic](https://alembic.sqlalchemy.org) |
| ИИ-генерация | [KIE AI](https://kie.ai) (nano-banana-2) |
| Изображения | [Pillow](https://pillow.readthedocs.io) (коллажи) |
| Оплата | Telegram Stars (XTR) |
| Прокси | aiohttp-socks |
| Конфиг | pydantic-settings + `.env` |

---

## ⚙️ Быстрый старт

### 1. Клонирование и окружение

```bash
git clone https://github.com/efimovand/bikeMeBot.git
cd bikeme

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Переменные окружения

```bash
cp .env.example .env
```

Заполни `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/motome
DATABASE_URL_SYNC=postgresql+psycopg2://user:password@localhost:5432/motome

BOT_TOKEN=your_telegram_bot_token

MEDIA_DIR=media

PROXY_TG_URL=http://user:password@host:port   # прокси для Telegram
PROXY_AI_URL=http://user:password@host:port   # прокси для KIE AI
```

### 3. База данных

```bash
alembic upgrade head
```

### 4. Запуск

```bash
python bot.py
```

---

## 🗄 Схема базы данных

```
location          bike ──── bike_color
                   │            │
                   └──── bike_file ──────────────────────┐
                                                         │
helmet ── helmet_color ── helmet_file ──────────────┐    │
jacket ── jacket_color ── jacket_file ──────────┐   │    │
suit   ── suit_color   ── suit_file   ──────┐   │   │    │
glove  ── glove_color  ── glove_file  ──┐   │   │   │    │
boot   ── boot_color   ── boot_file   ─┐│   │   │   │    │
                                       ││   │   │   │    │
user ◄─────────────────────────────────┘┘   │   │   │    │
 │   bike_file_id, helmet_file_id,          │   │   │    │
 │   jacket_file_id, suit_file_id,          │   │   │    │
 │   glove_file_id, boot_file_id,           │   │   │    │
 │   location_id, balance                   │   │   │    │
 │                                          │   │   │    │
 ├── user_photoset                          │   │   │    │
 │                                          │   │   │    │
 └── generation ◄───────────────────────────┘───┘───┘────┘
      (bike/helmet/jacket/suit/glove/boot_file_id,
       account_id, status, user_id)

account           dictionary_prompt        collage
(token, email,    (type, text —            (type, brand,
 is_active)        default/helmet/          model_id, file,
                   jacket/suit/…)           models_count)
```

---

## 💳 Монетизация

Бот использует **Telegram Stars** в качестве валюты:

| Пакет | Звёзды | Генерации | Скидка |
|---|---|---|---|
| Стартовый | ⭐️ 50 | 1 | — |
| Популярный | ⭐️ 150 | 5 | −40% |
| Выгодный | ⭐️ 450 | 20 | −55% |
| Максимум | ⭐️ 1750 | 100 | −65% |

Новым пользователям из списка приглашённых (`invited_users.json`) автоматически начисляется **50 генераций** при первом запуске.

---

## 🎨 Коллажи экипировки

При выборе снаряжения бот автоматически формирует **визуальные коллажи** из фото товаров:

- **Бренд-коллаж** — все модели бренда в сетке 3×N
- **Цвет-коллаж** — все расцветки выбранной модели

Коллажи **кешируются** в таблице `collage` и пересоздаются только при изменении каталога.

---

## 🔄 Ротация аккаунтов KIE AI

Бот поддерживает пул аккаунтов KIE AI. При исчерпании кредитов на одном аккаунте он автоматически деактивируется и выбирается следующий активный аккаунт.

```python
account = await db.get_active_account()   # random.choice из активных
# При InsufficientCreditsError:
await db.deactivate_account(account.id)   # → следующий аккаунт
```

---

## 📸 Требования к фото пользователя

Для качественной генерации необходимо загрузить **3 фотографии**:

| # | Ракурс | Требования |
|---|---|---|
| 1 | 👤 Анфас | Лицо и плечи, смотреть в камеру |
| 2 | 👤 Профиль | Боком (левый или правый) |
| 3 | 🧍 В полный рост | От головы до ног, прямо |

---

## 📋 Миграции

История миграций БД:

```
57dcb9bb  init — базовые таблицы (bike, helmet, user, generation…)
ab829c86  remove location_id from generation
ce72b6cf  add email to account
5bfe27be  add jackets
b987dcebd add collages table
c548331a  added gloves tables
f4fa1541  modified collage table (model_id)
51d20fa2  added boots tables
1471556e  added tables for suit
932de4fc  modified tables for location changing
8d49c607  added balance field to user
72819409  make balance NOT NULL
247770d4  logical grouping (no-op migration)
```

---

## 🤝 Contributing

1. Форкни репозиторий
2. Создай ветку: `git checkout -b feature/my-feature`
3. Закоммить изменения: `git commit -m 'feat: add my feature'`
4. Запушь ветку: `git push origin feature/my-feature`
5. Открой Pull Request

---

<div align="center">

Сделано с ❤️ и ☕ &nbsp;·&nbsp; [Telegram](https://t.me/bikeMeBot)

</div>
