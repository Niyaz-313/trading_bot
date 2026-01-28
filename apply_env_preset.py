"""
Применяет env preset к .env (с бэкапом), НЕ затирая секреты пользователя.

Проблема, которую решаем:
пресеты в репозитории специально содержат плейсхолдеры токенов (PASTE_...),
а прямое копирование пресета в .env затирает реальный TINVEST_TOKEN/Telegram и ломает запуск.

Пример:
  python apply_env_preset.py --preset env_presets/AGGRESSIVE_QUALITY.env --env .env
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import datetime


_PRESERVE_KEYS = {
    # Telegram
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    # T-Invest
    "TINVEST_TOKEN",
    "TINVEST_ACCOUNT_ID",
    "TINVEST_GRPC_TARGET",
}


def _is_placeholder(v: str) -> bool:
    s = str(v or "").strip()
    if not s:
        return True
    low = s.lower()
    return (
        "paste_" in low
        or "your_" in low
        or "example" in low
        or "token_here" in low
        or low in {"changeme", "replace_me"}
    )


def _read_env_kv(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    kv: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f.read().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                continue
            kv[k] = v
    return kv


_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _apply_preset_lines(preset_lines: list[str], existing_kv: dict[str, str]) -> tuple[list[str], list[str]]:
    """
    Возвращает (out_lines, preserved_keys)
    """
    preserved: list[str] = []
    out: list[str] = []

    for raw in preset_lines:
        m = _KEY_RE.match(raw)
        if not m:
            out.append(raw)
            continue

        key = m.group(1).strip()
        val = m.group(2).strip()

        if key in _PRESERVE_KEYS:
            existing_val = (existing_kv.get(key) or "").strip()
            # если у пользователя значение есть — сохраняем его, когда в пресете плейсхолдер/пусто
            if existing_val and _is_placeholder(val):
                out.append(f"{key}={existing_val}")
                preserved.append(key)
                continue

        out.append(f"{key}={val}")

    return out, preserved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", required=True, help="Path to preset env file (e.g. env_presets/AGGRESSIVE_QUALITY.env)")
    ap.add_argument("--env", default=".env", help="Target .env path")
    ap.add_argument("--no-backup", action="store_true", help="Do not create .env backup")
    args = ap.parse_args()

    preset = args.preset
    env_path = args.env

    if not os.path.exists(preset):
        raise SystemExit(f"Preset not found: {preset}")

    existing_kv = _read_env_kv(env_path)

    # Backup existing .env
    if os.path.exists(env_path) and not args.no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"{env_path}.bak_{ts}"
        shutil.copyfile(env_path, backup)
        print(f"✓ Backup: {backup}")

    with open(preset, "r", encoding="utf-8") as f:
        preset_lines = f.read().splitlines()

    out_lines, preserved = _apply_preset_lines(preset_lines, existing_kv)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"✓ Applied preset: {preset} -> {env_path}")
    if preserved:
        print(f"✓ Preserved from existing .env: {', '.join(sorted(set(preserved)))}")
    else:
        # если секретов в старом .env не было — предупредим
        missing = [k for k in sorted(_PRESERVE_KEYS) if k not in existing_kv]
        if missing:
            print(f"⚠ No existing secrets found to preserve: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




Проблема, которую решаем:
пресеты в репозитории специально содержат плейсхолдеры токенов (PASTE_...),
а прямое копирование пресета в .env затирает реальный TINVEST_TOKEN/Telegram и ломает запуск.

Пример:
  python apply_env_preset.py --preset env_presets/AGGRESSIVE_QUALITY.env --env .env
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import datetime


_PRESERVE_KEYS = {
    # Telegram
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    # T-Invest
    "TINVEST_TOKEN",
    "TINVEST_ACCOUNT_ID",
    "TINVEST_GRPC_TARGET",
}


def _is_placeholder(v: str) -> bool:
    s = str(v or "").strip()
    if not s:
        return True
    low = s.lower()
    return (
        "paste_" in low
        or "your_" in low
        or "example" in low
        or "token_here" in low
        or low in {"changeme", "replace_me"}
    )


def _read_env_kv(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    kv: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f.read().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                continue
            kv[k] = v
    return kv


_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _apply_preset_lines(preset_lines: list[str], existing_kv: dict[str, str]) -> tuple[list[str], list[str]]:
    """
    Возвращает (out_lines, preserved_keys)
    """
    preserved: list[str] = []
    out: list[str] = []

    for raw in preset_lines:
        m = _KEY_RE.match(raw)
        if not m:
            out.append(raw)
            continue

        key = m.group(1).strip()
        val = m.group(2).strip()

        if key in _PRESERVE_KEYS:
            existing_val = (existing_kv.get(key) or "").strip()
            # если у пользователя значение есть — сохраняем его, когда в пресете плейсхолдер/пусто
            if existing_val and _is_placeholder(val):
                out.append(f"{key}={existing_val}")
                preserved.append(key)
                continue

        out.append(f"{key}={val}")

    return out, preserved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", required=True, help="Path to preset env file (e.g. env_presets/AGGRESSIVE_QUALITY.env)")
    ap.add_argument("--env", default=".env", help="Target .env path")
    ap.add_argument("--no-backup", action="store_true", help="Do not create .env backup")
    args = ap.parse_args()

    preset = args.preset
    env_path = args.env

    if not os.path.exists(preset):
        raise SystemExit(f"Preset not found: {preset}")

    existing_kv = _read_env_kv(env_path)

    # Backup existing .env
    if os.path.exists(env_path) and not args.no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"{env_path}.bak_{ts}"
        shutil.copyfile(env_path, backup)
        print(f"✓ Backup: {backup}")

    with open(preset, "r", encoding="utf-8") as f:
        preset_lines = f.read().splitlines()

    out_lines, preserved = _apply_preset_lines(preset_lines, existing_kv)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"✓ Applied preset: {preset} -> {env_path}")
    if preserved:
        print(f"✓ Preserved from existing .env: {', '.join(sorted(set(preserved)))}")
    else:
        # если секретов в старом .env не было — предупредим
        missing = [k for k in sorted(_PRESERVE_KEYS) if k not in existing_kv]
        if missing:
            print(f"⚠ No existing secrets found to preserve: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




Проблема, которую решаем:
пресеты в репозитории специально содержат плейсхолдеры токенов (PASTE_...),
а прямое копирование пресета в .env затирает реальный TINVEST_TOKEN/Telegram и ломает запуск.

Пример:
  python apply_env_preset.py --preset env_presets/AGGRESSIVE_QUALITY.env --env .env
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import datetime


_PRESERVE_KEYS = {
    # Telegram
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    # T-Invest
    "TINVEST_TOKEN",
    "TINVEST_ACCOUNT_ID",
    "TINVEST_GRPC_TARGET",
}


def _is_placeholder(v: str) -> bool:
    s = str(v or "").strip()
    if not s:
        return True
    low = s.lower()
    return (
        "paste_" in low
        or "your_" in low
        or "example" in low
        or "token_here" in low
        or low in {"changeme", "replace_me"}
    )


def _read_env_kv(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    kv: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f.read().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                continue
            kv[k] = v
    return kv


_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _apply_preset_lines(preset_lines: list[str], existing_kv: dict[str, str]) -> tuple[list[str], list[str]]:
    """
    Возвращает (out_lines, preserved_keys)
    """
    preserved: list[str] = []
    out: list[str] = []

    for raw in preset_lines:
        m = _KEY_RE.match(raw)
        if not m:
            out.append(raw)
            continue

        key = m.group(1).strip()
        val = m.group(2).strip()

        if key in _PRESERVE_KEYS:
            existing_val = (existing_kv.get(key) or "").strip()
            # если у пользователя значение есть — сохраняем его, когда в пресете плейсхолдер/пусто
            if existing_val and _is_placeholder(val):
                out.append(f"{key}={existing_val}")
                preserved.append(key)
                continue

        out.append(f"{key}={val}")

    return out, preserved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", required=True, help="Path to preset env file (e.g. env_presets/AGGRESSIVE_QUALITY.env)")
    ap.add_argument("--env", default=".env", help="Target .env path")
    ap.add_argument("--no-backup", action="store_true", help="Do not create .env backup")
    args = ap.parse_args()

    preset = args.preset
    env_path = args.env

    if not os.path.exists(preset):
        raise SystemExit(f"Preset not found: {preset}")

    existing_kv = _read_env_kv(env_path)

    # Backup existing .env
    if os.path.exists(env_path) and not args.no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"{env_path}.bak_{ts}"
        shutil.copyfile(env_path, backup)
        print(f"✓ Backup: {backup}")

    with open(preset, "r", encoding="utf-8") as f:
        preset_lines = f.read().splitlines()

    out_lines, preserved = _apply_preset_lines(preset_lines, existing_kv)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"✓ Applied preset: {preset} -> {env_path}")
    if preserved:
        print(f"✓ Preserved from existing .env: {', '.join(sorted(set(preserved)))}")
    else:
        # если секретов в старом .env не было — предупредим
        missing = [k for k in sorted(_PRESERVE_KEYS) if k not in existing_kv]
        if missing:
            print(f"⚠ No existing secrets found to preserve: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


