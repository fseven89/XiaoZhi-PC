# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: Triple Inbox Listener (Telegram Bot via Cloudflare Worker + Local Wi-Fi 8787 + ntfy.sh)

import os, time, json, datetime, threading, email, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

BASE_DIR = r"C:\XiaoZhi-PC"
INBOX_DIR = os.path.join(BASE_DIR, "workspace", "inbox")
OWNER_FILE = os.path.join(BASE_DIR, "logs", "tg_owner_id.txt")
os.makedirs(INBOX_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, ".env"))

NTFY_TOPIC = os.getenv("PHONE_NTFY_TOPIC", "").strip()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_API_BASE = os.getenv("TELEGRAM_API_BASE", "https://" + "api.telegram.org").strip().rstrip("/")

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JOHNNY // INBOX 2077</title>
<style>
body{background:#0d0d12;color:#fcee0a;font-family:monospace;padding:20px;text-align:center}
.box{border:2px solid #ff003c;padding:20px;border-radius:8px;max-width:420px;margin:auto;background:#16161f}
input,button{width:100%;margin-top:15px;padding:12px;font-size:16px;border-radius:4px;border:none}
button{background:#fcee0a;color:#000;font-weight:bold;cursor:pointer}
.ok{color:#00ff9f;margin-top:15px}
</style></head><body><div class="box">
<h2>⚡ XIAOZHI // INBOX</h2>
<p>Скинь фото с камеры или файл напрямую в память Джонни</p>
<form method="POST" enctype="multipart/form-data">
<input type="file" name="file" accept="image/*,.txt,.md,.pdf,.log,.py" required>
<button type="submit">ОТПРАВИТЬ ДЖОННИ</button>
</form>STATUS_MSG</div></body></html>"""

class LocalUploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.replace("STATUS_MSG", "").encode("utf-8"))

    def do_POST(self):
        ctype = self.headers.get("Content-Type", "")
        clen = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(clen)
        msg = ""
        if "multipart/form-data" in ctype:
            raw_msg = f"Content-Type: {ctype}\r\n\r\n".encode("utf-8") + body
            parsed = email.message_from_bytes(raw_msg)
            for part in parsed.walk():
                fname = part.get_filename()
                if fname:
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = os.path.basename(fname)
                    save_path = os.path.join(INBOX_DIR, f"{ts}_{safe_name}")
                    with open(save_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    msg = f'<div class="ok">✅ Принято: {safe_name}<br>Теперь скажи колонке: «Джонни, сделай анализ фото!»</div>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.replace("STATUS_MSG", msg).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def get_allowed_user_id() -> int:
    env_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
    if env_id.isdigit():
        return int(env_id)
    if os.path.exists(OWNER_FILE):
        try:
            val = open(OWNER_FILE, "r", encoding="utf-8").read().strip()
            if val.isdigit():
                return int(val)
        except Exception:
            pass
    return 0

def save_owner_id(uid: int):
    try:
        with open(OWNER_FILE, "w", encoding="utf-8") as f:
            f.write(str(uid))
    except Exception:
        pass

def tg_reply(chat_id: int, text: str):
    if not TG_TOKEN:
        return
    try:
        requests.post(f"{TG_API_BASE}/bot{TG_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception:
        pass

def tg_download_file(file_id: str, target_path: str) -> bool:
    try:
        r_info = requests.get(f"{TG_API_BASE}/bot{TG_TOKEN}/getFile?file_id={file_id}", timeout=15)
        if not r_info.ok:
            return False
        file_path = r_info.json()["result"]["file_path"]
        r_bin = requests.get(f"{TG_API_BASE}/file/bot{TG_TOKEN}/{file_path}", timeout=60)
        if r_bin.ok:
            with open(target_path, "wb") as f:
                f.write(r_bin.content)
            return True
    except Exception:
        pass
    return False

def telegram_loop():
    if not TG_TOKEN:
        return
    offset = 0
    while True:
        try:
            r = requests.get(f"{TG_API_BASE}/bot{TG_TOKEN}/getUpdates?timeout=40&offset={offset}", timeout=50)
            if not r.ok:
                time.sleep(5)
                continue
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                sender_id = msg.get("from", {}).get("id", 0)
                chat_id = msg.get("chat", {}).get("id", 0)
                allowed_id = get_allowed_user_id()
                if allowed_id == 0 and sender_id:
                    save_owner_id(sender_id)
                    allowed_id = sender_id
                if sender_id != allowed_id:
                    continue

                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                if "photo" in msg and msg["photo"]:
                    best_photo = next(iter(reversed(msg["photo"])))
                    fname = f"{ts}_tg_photo.jpg"
                    fpath = os.path.join(INBOX_DIR, fname)
                    if tg_download_file(best_photo["file_id"], fpath):
                        tg_reply(chat_id, f"✅ Фото принято в inbox Джонни ({fname}). Скажи колонке: «Сделай анализ фото».")
                elif "document" in msg:
                    doc = msg["document"]
                    orig = doc.get("file_name", "document.bin")
                    fname = f"{ts}_{orig}"
                    fpath = os.path.join(INBOX_DIR, fname)
                    if tg_download_file(doc["file_id"], fpath):
                        tg_reply(chat_id, f"✅ Файл принят в inbox Джонни ({fname}).")
                elif "text" in msg:
                    txt = msg["text"]
                    if txt.strip() == "/start":
                        tg_reply(chat_id, "⚡ Johnny PC bridge на связи! Скидывай сюда фото (до 20 МБ), схемы или файлы для анализа.")
                    else:
                        fname = f"{ts}_tg_note.txt"
                        with open(os.path.join(INBOX_DIR, fname), "w", encoding="utf-8") as tf:
                            tf.write(txt)
                        tg_reply(chat_id, f"✅ Заметка сохранена в inbox ({fname}).")
        except Exception:
            time.sleep(5)

def ntfy_loop():
    if not NTFY_TOPIC:
        return
    in_topic = f"{NTFY_TOPIC}_in"
    stream_url = "https://" + "ntfy.sh" + f"/{in_topic}/json"
    while True:
        try:
            with requests.get(stream_url, stream=True, timeout=90) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line.decode("utf-8", errors="replace"))
                    if data.get("event") != "message":
                        continue
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    msg_text = data.get("message", "")
                    att = data.get("attachment")
                    if att and att.get("url"):
                        orig_name = att.get("name", f"file_{ts}.bin")
                        save_path = os.path.join(INBOX_DIR, f"{ts}_{orig_name}")
                        file_resp = requests.get(att["url"], timeout=30)
                        if file_resp.ok:
                            with open(save_path, "wb") as f:
                                f.write(file_resp.content)
                    elif msg_text:
                        save_path = os.path.join(INBOX_DIR, f"{ts}_note.txt")
                        with open(save_path, "w", encoding="utf-8") as f:
                            f.write(msg_text)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=telegram_loop, daemon=True).start()
    threading.Thread(target=ntfy_loop, daemon=True).start()
    HTTPServer(("0.0.0.0", 8787), LocalUploadHandler).serve_forever()