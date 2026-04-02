import pyautogui
import time
import json


COORDS_FILE = "coords.json"

DEFAULT_COORDS = {
    "plus_btn": (0, 0),
    "upload_btn": (0, 0),
    "prompt_field": (0, 0),
    "more_btn": (0, 0),
    "download_btn": (0, 0),
}


def load_coords():
    try:
        with open(COORDS_FILE, "r") as f:
            data = json.load(f)
            return {k: tuple(v) for k, v in data.items()}
    except FileNotFoundError:
        return DEFAULT_COORDS.copy()


def save_coords(coords):
    with open(COORDS_FILE, "w") as f:
        json.dump(coords, f)


def run_calibration():
    """Интерактивная калибровка координат элементов."""
    coords = {}

    elements = [
        ("plus_btn",     "1. Кнопка '+' (для вложений)"),
        ("upload_btn",   "2. Кнопка 'Upload files' в меню"),
        ("prompt_field", "3. Поле ввода промпта"),
        ("more_btn",     "4. Кнопка '⋮' под результатом"),
        ("download_btn", "5. Кнопка скачивания результата"),
    ]

    print("=== Калибровка координат AI Studio / Gemini ===\n")
    for key, label in elements:
        print(f"Наведи мышь на: {label}")
        time.sleep(5)
        coords[key] = pyautogui.position()

    save_coords(coords)
    print("✅ Калибровка завершена!")

    return coords


def show_current_coords():
    while True:
        time.sleep(5)
        coords = pyautogui.position()
        print(f"Текущие координаты: X={coords.x}, Y={coords.y}")


if __name__ == '__main__':
    # run_calibration()
    show_current_coords()
