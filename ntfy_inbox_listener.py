# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: Two-Way Phone Inbox Listener (receives photos & files from Poco F7 via ntfy)

import os, time, json, datetime, requests
from dotenv import load_dotenv

BASE_DIR = r"C:\XiaoZhi-PC"
INBOX_DIR = os.path.join(BASE_DIR, "workspace", "inbox")
os.makedirs(INBOX_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOPIC = os.getenv("PHONE_NTFY_TOPIC", "").strip()

def listen_loop():
    if not TOPIC:
        return
    in_topic = f"{TOPIC}_in"
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
    listen_loop()