# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
# Module: Cloud Sentinel & Failover Monitor (24/7 VPS Node)

import os, time, threading, datetime, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

HEARTBEAT_SECRET = os.getenv("CLOUD_HEARTBEAT_SECRET", "johnny_sbge_2077").strip()
NTFY_TOPIC = os.getenv("PHONE_NTFY_TOPIC", "").strip()
TIMEOUT_SEC = 90  # Тревога, если домашний ПК молчит дольше 90 секунд

last_ping = time.time()
home_online = True

def send_alert(msg: str):
    if not NTFY_TOPIC:
        return
    try:
        url = "https://" + "ntfy.sh" + f"/{NTFY_TOPIC}?title=XiaoZhi-SBGE-Alert&priority=high&tags=rotating_light"
        requests.post(url, data=msg.encode("utf-8"), timeout=10)
    except Exception:
        pass

class HeartbeatHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global last_ping, home_online
        if self.path == "/heartbeat":
            token = self.headers.get("X-SBGE-Token", "")
            if token == HEARTBEAT_SECRET:
                last_ping = time.time()
                if not home_online:
                    home_online = True
                    send_alert("Домашний узел XiaoZhi-PC вернулся в сеть. Штатный режим СБГЭ восстановлен.")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                return
        self.send_response(403)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def watchdog_loop():
    global home_online
    while True:
        time.sleep(15)
        if home_online and (time.time() - last_ping > TIMEOUT_SEC):
            home_online = False
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            send_alert(f"[{ts}] АВР СБГЭ: Потерян пульс домашнего ПК! Облачный контур переведен в режим дежурства.")

if __name__ == "__main__":
    threading.Thread(target=watchdog_loop, daemon=True).start()
    print("[Cloud Sentinel] Порт 8765 открыт для приема телеметрии от домашнего ПК...")
    HTTPServer(("0.0.0.0", 8765), HeartbeatHandler).serve_forever()