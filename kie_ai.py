import asyncio
import base64
import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Optional

import aiohttp
from config import settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

API_UPLOAD = "https://kieai.redpandaai.co/api/file-base64-upload"
API_CREATE = "https://api.kie.ai/api/v1/jobs/createTask"
API_STATUS = "https://api.kie.ai/api/v1/jobs/recordInfo"

PROXY = settings.proxy_ai_url
BASE_DIR = Path(settings.media_dir)


# ---------------------------------------------------------------------------
# HTTP-сессия
# ---------------------------------------------------------------------------

def make_session() -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    return aiohttp.ClientSession(timeout=timeout)


# ---------------------------------------------------------------------------
# Загрузка файлов
# ---------------------------------------------------------------------------

async def upload_file(
    session: aiohttp.ClientSession,
    path: str | Path,
    api_key: str,
    file_name: str | None = None,
) -> str:
    path = Path(path)
    upload_name = file_name or path.name

    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/jpeg"

    data_url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    logger.info(
        "Uploading %s as '%s' (%.1f MB as base64)...",
        path.name, upload_name, len(data_url) / 1024 / 1024,
    )

    async with session.post(
        API_UPLOAD,
        proxy=PROXY,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "base64Data": data_url,
            "uploadPath": "bikemebot/uploads",
            "fileName": upload_name,
        },
    ) as resp:
        data = await resp.json()
        if not data.get("success") or data.get("code") != 200:
            raise RuntimeError(f"Upload failed [{upload_name}]: {data}")
        url = data["data"]["downloadUrl"]
        logger.info("Uploaded '%s' → %s", upload_name, url)
        return url


async def upload_files(
    items: list[...],
    api_key: str,
) -> list[str]:
    async with make_session() as s:
        tasks = [
            upload_file(s, path, api_key, name)
            for path, name in (
                (i if isinstance(i, tuple) else (i, None)) for i in items
            )
        ]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Запуск задачи
# ---------------------------------------------------------------------------

class InsufficientCreditsError(Exception):
    pass


class ContentPolicyError(Exception):
    pass


async def create_task(
    image_urls: list[str],
    prompt: str,
    api_key: str,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    output_format: str = "jpg",
) -> str:
    async with make_session() as s:
        async with s.post(
            API_CREATE,
            proxy=PROXY,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={
                "model": "nano-banana-2",
                "input": {
                    "prompt": prompt,
                    "image_input": image_urls,
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "output_format": output_format,
                },
            },
        ) as resp:
            data = await resp.json()
            logger.info("CreateTask response: %s", data)
            if data.get("code") == 402:
                raise InsufficientCreditsError()
            if resp.status != 200 or data.get("code") != 200:
                raise RuntimeError(f"CreateTask failed: {data}")
            task_id = data["data"]["taskId"]
            logger.info("Task created: %s", task_id)
            return task_id


# ---------------------------------------------------------------------------
# Поллинг
# ---------------------------------------------------------------------------

async def poll_until_done(task_id: str, api_key: str, interval: int = 15) -> list[str]:
    async with make_session() as s:
        while True:
            async with s.get(
                API_STATUS,
                proxy=PROXY,
                headers={"Authorization": f"Bearer {api_key}"},
                params={"taskId": task_id},
            ) as resp:
                data = await resp.json()

            state = (data.get("data") or {}).get("state", "unknown")
            logger.info("State: %s", state)

            if state in ("waiting", "queuing", "generating"):
                await asyncio.sleep(interval)
                continue
            if state == "fail":
                fail_msg = (data.get("data") or {}).get("failMsg", "")
                if "filtered out" in fail_msg or "Prohibited Use policy" in fail_msg:
                    raise ContentPolicyError()
                raise RuntimeError(f"Generation failed: {fail_msg}")
            if state == "success":
                result_json = json.loads(
                    (data.get("data") or {}).get("resultJson") or "{}"
                )
                urls = result_json.get("resultUrls") or []
                if not urls:
                    raise RuntimeError("No resultUrls in response")
                return urls

            raise RuntimeError(f"Unexpected state: {state}")


# ---------------------------------------------------------------------------
# Основная функция генерации для бота
# ---------------------------------------------------------------------------

async def generate_for_user(
    generation_id: int,
    tg_id: int,
    api_key: str,
    bike_file_path: str | Path,
    helmet_file_path: Optional[str | Path] = None,
    prompt: str = "",
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    output_format: str = "jpg",
) -> Path:
    from database import get_user_by_tg_id

    user = await get_user_by_tg_id(tg_id)
    if user is None or user.photoset is None:
        raise ValueError(f"Пользователь tg_id={tg_id} не найден или нет фотосета")

    ts = int(time.time())
    user_dir = BASE_DIR / "users" / str(tg_id)

    items: list[tuple[str | Path, str | None]] = [
        (bike_file_path, None),
        (BASE_DIR / user.photoset.front_photo, f"{tg_id}_front_{ts}.jpg"),
        (BASE_DIR / user.photoset.side_photo, f"{tg_id}_side_{ts}.jpg"),
        (BASE_DIR / user.photoset.body_photo, f"{tg_id}_body_{ts}.jpg"),
    ]
    if helmet_file_path:
        items.append((helmet_file_path, None))

    logger.info("generate_for_user generation_id=%s tg_id=%s: uploading %d files...", generation_id, tg_id, len(items))

    image_urls = await upload_files(items, api_key=api_key)
    task_id = await create_task(image_urls, prompt, api_key, aspect_ratio, resolution, output_format)
    result_urls = await poll_until_done(task_id, api_key=api_key)

    output_dir = user_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"result_{generation_id}.jpg"

    async with make_session() as s:
        async with s.get(result_urls[0], proxy=PROXY) as resp:
            resp.raise_for_status()
            out_path.write_bytes(await resp.read())

    logger.info("Generation %s saved to %s", generation_id, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Ручной запуск для тестов
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BASE_TEST = Path(r"C:\users\masha\Desktop\bikeMeBot\media")

    from prompts import make_final_prompt

    async def _test():
        prompt = await make_final_prompt(bike_file_id=1, helmet_file_id=1)
        path = await generate_for_user(
            generation_id=0,
            tg_id=0,
            bike_file_path=BASE_TEST / "bikes/ducati/panigalev2/panigalev2_red.jpg",
            helmet_file_path=BASE_TEST / "helmets/ls2/xforce/xforce_black.jpg",
            prompt=prompt,
            aspect_ratio="1:1",
            resolution="1K",
        )
        print(f"\nСохранено: {path.resolve()}")

    asyncio.run(_test())
