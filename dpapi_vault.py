# Copyright (c) 2026 Курчицикий М.С (fseven89). All rights reserved.
import base64, json, os, subprocess
from pathlib import Path

BASE_DIR = Path(r"C:\XiaoZhi-PC")
ENV_PATH = BASE_DIR / ".env"
VAULT_PATH = BASE_DIR / "vault.dpapi"

def seal_env_to_dpapi() -> str:
    """Шифрует пары KEY=VALUE из .env в vault.dpapi через Windows DPAPI (CurrentUser)."""
    if not ENV_PATH.exists():
        return "Файл .env не найден."
    secrets = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        secrets[k.strip()] = v.strip().strip('"').strip("'")

    raw_json = json.dumps(secrets, ensure_ascii=False)
    b64_plain = base64.b64encode(raw_json.encode("utf-8")).decode("ascii")
    ps = (
        "Add-Type -AssemblyName System.Security; "
        f"$bytes = [Convert]::FromBase64String('{b64_plain}'); "
        "$enc = [System.Security.Cryptography.ProtectedData]::Protect($bytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser); "
        "[Convert]::ToBase64String($enc)"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
    if res.returncode != 0 or not res.stdout.strip():
        return f"Ошибка DPAPI Protect: {res.stderr.strip()}"
    VAULT_PATH.write_text(res.stdout.strip(), encoding="ascii")
    return f"Зашифровано {len(secrets)} секретов в vault.dpapi (Windows DPAPI CurrentUser)."

def load_dpapi_into_environ() -> int:
    """Расшифровывает vault.dpapi в память процесса os.environ без записи на диск."""
    if not VAULT_PATH.exists():
        return 0
    b64_enc = VAULT_PATH.read_text(encoding="ascii").strip()
    if not b64_enc:
        return 0
    ps = (
        "Add-Type -AssemblyName System.Security; "
        f"$enc = [Convert]::FromBase64String('{b64_enc}'); "
        "$dec = [System.Security.Cryptography.ProtectedData]::Unprotect($enc, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser); "
        "[Convert]::ToBase64String($dec)"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
    if res.returncode != 0 or not res.stdout.strip():
        return 0
    raw_json = base64.b64decode(res.stdout.strip()).decode("utf-8")
    secrets = json.loads(raw_json)
    for k, v in secrets.items():
        if v:
            os.environ[k] = v
    return len(secrets)

if __name__ == "__main__":
    print(seal_env_to_dpapi())
    print("Проверка расшифровки в память:", load_dpapi_into_environ(), "ключей")