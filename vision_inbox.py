# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: Smart Multimodal Vision & Phone Inbox Analyzer

import os, base64, glob, requests
import failover_power_grid as sbge

WORKSPACE_DIR = r"C:\XiaoZhi-PC\workspace"
INBOX_DIR = os.path.join(WORKSPACE_DIR, "inbox")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")

def analyze_latest(question: str = "Сделай подробный технический анализ этого фото или файла.") -> str:
    if not os.path.exists(INBOX_DIR):
        return "Папка входящих workspace/inbox пуста."
    all_files = sorted([f for f in glob.glob(os.path.join(INBOX_DIR, "*")) if os.path.isfile(f)], key=os.path.getmtime, reverse=True)
    if not all_files:
        return "Во входящих (workspace/inbox) пока нет новых файлов."

    img_files = [f for f in all_files if f.lower().endswith(IMG_EXTS)]
    txt_files = [f for f in all_files if f.lower().endswith(".txt")]

    # Если есть свежее фото — берем его, а свежий текст рядом используем как дополнительный контекст
    target = img_files[0] if img_files else all_files[0]
    fname = os.path.basename(target)
    _, ext_raw = os.path.splitext(target)
    ext = ext_raw.lower()

    extra_note = ""
    if img_files and txt_files:
        # Если текстовая заметка пришла в пределах 15 минут от фото — добавляем её к вопросу
        if abs(os.path.getmtime(txt_files[0]) - os.path.getmtime(target)) < 900:
            try:
                extra_note = open(txt_files[0], "r", encoding="utf-8", errors="replace").read().strip()
            except Exception:
                pass

    full_q = f"{question} (Комментарий владельца: {extra_note})" if extra_note else question

    if ext in IMG_EXTS:
        api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return "Для анализа фото нужен LLM_API_KEY в .env."
        with open(target, "rb") as img_f:
            b64_img = base64.b64encode(img_f.read()).decode("ascii")
        mime = "image/png" if ext == ".png" else "image/jpeg"
        url = "https://" + "api.proxyapi" + ".ru/v1/chat/completions"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Ты — точный технический эксперт. Проанализируй изображение ({fname}). Задача: {full_q}. Ответь строго по фактам на русском языке."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_img}"}}
                    ]
                }],
                "temperature": 0.1
            },
            timeout=45
        )
        if not resp.ok:
            return f"Ошибка Vision API ({resp.status_code}): {resp.text[:250]}"
        first_choice = next(iter(resp.json().get("choices", [])), {})
        ans = first_choice.get("message", {}).get("content", "").strip()
        with open(os.path.join(WORKSPACE_DIR, "last_vision_analysis.md"), "w", encoding="utf-8") as wf:
            wf.write(f"# Анализ фото {fname}\n\n{ans}")
        return f"[Анализ фото: {fname}]\n{ans}"

    with open(target, "r", encoding="utf-8", errors="replace") as tf:
        content = tf.read()[:12000]
    res = sbge.execute_with_avr(f"Файл: {fname}\nЗадача: {full_q}\n\nСодержимое:\n{content}")
    with open(os.path.join(WORKSPACE_DIR, "last_file_analysis.md"), "w", encoding="utf-8") as wf:
        wf.write(f"# Анализ файла {fname}\n\n{res['answer']}")
    return f"[Анализ файла: {fname} | {res['line']}]\n{res['answer']}"