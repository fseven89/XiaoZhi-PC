# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: Multimodal Vision & Phone Inbox Analyzer

import os, base64, glob, requests
import failover_power_grid as sbge

WORKSPACE_DIR = r"C:\XiaoZhi-PC\workspace"
INBOX_DIR = os.path.join(WORKSPACE_DIR, "inbox")

def analyze_latest(question: str = "Сделай подробный технический анализ этого фото или файла.") -> str:
    if not os.path.exists(INBOX_DIR):
        return "Папка входящих workspace/inbox пуста. Отправь фото или файл в топик _in приложения ntfy на телефоне."
    files = sorted([f for f in glob.glob(os.path.join(INBOX_DIR, "*")) if os.path.isfile(f)], key=os.path.getmtime, reverse=True)
    if not files:
        return "Во входящих (workspace/inbox) пока нет новых файлов."

    latest = next(iter(files))
    fname = os.path.basename(latest)
    _, ext_raw = os.path.splitext(latest)
    ext = ext_raw.lower()

    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            return "Для анализа фото нужен LLM_API_KEY в .env."
        with open(latest, "rb") as img_f:
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
                        {"type": "text", "text": f"Ты — точный технический эксперт. Проанализируй фото ({fname}). Задача: {question}. Ответь строго по фактам на русском языке."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_img}"}}
                    ]
                }],
                "temperature": 0.1
            },
            timeout=45
        )
        if not resp.ok:
            return f"Ошибка Vision API ({resp.status_code}): {resp.text[:200]}"
        first_choice = next(iter(resp.json().get("choices", [])), {})
        ans = first_choice.get("message", {}).get("content", "").strip()
        with open(os.path.join(WORKSPACE_DIR, "last_vision_analysis.md"), "w", encoding="utf-8") as wf:
            wf.write(f"# Анализ фото {fname}\n\n{ans}")
        return f"[Анализ фото: {fname}]\n{ans}"

    with open(latest, "r", encoding="utf-8", errors="replace") as tf:
        content = tf.read()[:12000]
    res = sbge.execute_with_avr(f"Файл: {fname}\nЗадача: {question}\n\nСодержимое:\n{content}")
    with open(os.path.join(WORKSPACE_DIR, "last_file_analysis.md"), "w", encoding="utf-8") as wf:
        wf.write(f"# Анализ файла {fname}\n\n{res['answer']}")
    return f"[Анализ файла: {fname} | {res['line']}]\n{res['answer']}"