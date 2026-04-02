import pyautogui
import pygetwindow as gw
import pyperclip
import time
from coords import load_coords, run_calibration


# ---------------------------------------------------------------------------
# Координаты элементов AI Studio / Gemini
# ---------------------------------------------------------------------------

COORDS = {}

PROMPT = """You are given 3 photos of the same real person (front face, side profile, full body),
1 photo of a motorcycle,
and additional photos of a motorcycle helmet.
Generate a photorealistic 8K image of THIS EXACT person sitting on THIS EXACT motorcycle.
Requirements:
Preserve the person's exact facial features, face shape, skin tone, and hair color (face must remain clearly recognizable)
Preserve the exact motorcycle model, color, and all details
Use the provided helmet on the person (accurately matching its design, color, and details)
The helmet can be either worn or held, but must not fully obscure the face (face should remain visible).
Person is sitting naturally on the motorcycle, hands on handlebars
Night city street background with bokeh lights, cinematic lighting
Photorealistic style, not illustration or painting
Full body shot showing both person and complete motorcycle. 
The motorcycle and the person must be completely in the frame."""


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def focus_chrome():
    windows = gw.getWindowsWithTitle("Google AI Studio") or gw.getWindowsWithTitle("Google Gemini")
    if not windows:
        raise Exception("Окно AI Studio не найдено! Открой его вручную.")
    windows[0].activate()
    time.sleep(0.5)


def upload_file(filepath: str):
    pyautogui.click(*COORDS["plus_btn"])
    time.sleep(0.8)

    pyautogui.click(*COORDS["upload_btn"])
    time.sleep(1.5)

    pyautogui.typewrite(filepath, interval=0.01)
    pyautogui.press("enter")
    time.sleep(1.5)


def type_prompt(text: str):
    pyautogui.click(*COORDS["prompt_field"])
    time.sleep(0.3)
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)


def run_generation():
    pyautogui.hotkey("ctrl", "enter")


def scroll_to_bottom():
    focus_chrome()
    pyautogui.hotkey("ctrl", "end")


def wait_and_download(max_wait: int = 60):
    print(f"⏳ Ждём генерацию...")

    # Обнаружение завершения генерации
    start_time = time.time()
    while True:
        try:
            location = pyautogui.locateOnScreen(
                r'C:\Users\masha\Desktop\bikeMeBot\autogui\references\generation_completed.png',
                # region=(690, 680, 770, 360)
            )
            if location:
                print("✅ Плашка найдена!")
                break

            if time.time() - start_time > max_wait:
                raise Exception("⏱ Таймаут ожидания генерации")
        except pyautogui.ImageNotFoundException:
            print("Плашка не найдена")
            scroll_to_bottom()
            time.sleep(5)

    # Скачивание результата
    scroll_to_bottom()
    time.sleep(1)

    pyautogui.click(*COORDS["more_btn"])
    time.sleep(0.8)

    pyautogui.click(*COORDS["download_btn"])
    time.sleep(10)

    pyautogui.typewrite(f"generated_file_{time.time()}", interval=0.01)
    pyautogui.press("enter")
    time.sleep(1.5)

    print("✅ Результат скачан!")


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------

def generate(
    bike_path: str,
    front_path: str,
    side_path: str,
    body_path: str,
    helmet_path: str | None = None,
    prompt: str = PROMPT,
    wait: int = 60,
):
    focus_chrome()
    time.sleep(0.5)

    files = [bike_path]
    if helmet_path:
        files.append(helmet_path)
    files += [front_path, side_path, body_path]

    for filepath in files:
        upload_file(filepath)

    type_prompt(prompt)
    time.sleep(3)

    run_generation()
    print("✅ Генерация запущена!")

    wait_and_download(max_wait=wait)


def start(calibrate: bool = False):
    global COORDS
    COORDS = run_calibration() if calibrate else load_coords()

    print("\nНачало автоматизации через 3..2..1.. ")
    time.sleep(3)

    generate(
        bike_path=r"C:\Users\masha\Desktop\bikeMeBot\media\bikes\honda\goldwing\goldwing_beige.jpg",
        helmet_path=r"C:\Users\masha\Desktop\bikeMeBot\media\helmets\agv\k1s\k1s_white.jpg",
        front_path=r"C:\Users\masha\Desktop\bikeMeBot\media\users\test\front.jpg",
        side_path=r"C:\Users\masha\Desktop\bikeMeBot\media\users\test\side.jpg",
        body_path=r"C:\Users\masha\Desktop\bikeMeBot\media\users\test\body.jpg",
    )


if __name__ == "__main__":
    start(calibrate=False)
