import cv2
import ollama
from PIL import Image
import tempfile
import os
import time
import re
from modules.devices import camera_settings
from modules.language import detect_language


def vision_prompt(question):
    """The small camera model works best with English visual instructions."""
    if detect_language(question) != "id":
        return question
    if re.search(r"\b(?:baca|bacakan|teks|tulisan)\b", question, re.I):
        return "Read the text visible in this image."
    if re.search(r"\bwarna\b", question, re.I):
        return "What color is the main object in this image?"
    if re.search(r"\b(?:penampilanku|penampilan)\b", question, re.I):
        return "Describe the visible person's appearance in this image."
    return "Briefly describe what you can see in this image."

def capture_image():
    index, backend = camera_settings()
    cam = cv2.VideoCapture(index, backend)
    try:
        ret, frame = cam.read()
    finally:
        cam.release()
    if not ret:
        return None
    return frame

def capture_and_analyze(question):
    print("[VISION] Capturing image...")
    frame = capture_image()
    if frame is None:
        return "I cannot access the camera."

    # Convert to PIL and show on interface overlay
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    try:
        from modules.interface import show_capture, clear_capture
        show_capture(pil_image)
    except Exception:
        pass  # interface not running, skip overlay

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_path = tmp.name
    tmp.close()

    cv2.imwrite(tmp_path, frame)

    try:
        # CPU-only laptops can need about 50 seconds to load the model the first time.
        response = ollama.Client(timeout=120).chat(
            model="moondream",
            options={"num_predict": 96, "num_ctx": 2048},
            keep_alive="5m",
            messages=[{
                "role": "user",
                "content": vision_prompt(question),
                "images": [tmp_path]
            }]
        )
        return response["message"]["content"]
    except Exception as e:
        print(f"[VISION] Error: {e}")
        return "I could not analyze the image."
    finally:
        for _ in range(5):
            try:
                os.remove(tmp_path)
                break
            except PermissionError:
                time.sleep(0.2)
        # Clear the overlay once analysis is done
        try:
            from modules.interface import clear_capture
            clear_capture()
        except Exception:
            pass
