"""
Обновляет строку SYMBOLS= в .env (или добавляет её, если отсутствует).

Использование:
  python update_env_symbols.py
  python update_env_symbols.py --symbols "SBER,GAZP,VTBR,..."

По умолчанию ставит список из 10+ российских тикеров.
"""

from __future__ import annotations

import argparse
import os

# База ликвидных акций РФ + доп. “сырьевые” (нефть/металлы) + валютные инструменты/ETF
DEFAULT_SYMBOLS = "SBER,GAZP,YNDX,VTBR,MOEX,LKOH,ROSN,NVTK,GMKN,TATN,MGNT,AFLT,SNGS,SNGSP,CHMF,NLMK,MAGN,MTSS,IRAO,ALRS,PHOR,PLZL,RUAL,AFKS,TRNFP,SIBN,FLOT,BANE,BANEP,RNFT,TATNP,SELG,UGLD,LNZL,USD000UTSTOM,CNYRUB_TOM,GLDRUB_TOM,SLVRUB_TOM,PLTRUB_TOM,PLDRUB_TOM"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env", help="Path to .env file")
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS, help="Comma-separated tickers")
    args = ap.parse_args()

    env_path = args.env
    symbols = args.symbols.strip()

    if not symbols:
        raise SystemExit("symbols is empty")

    if not os.path.exists(env_path):
        raise SystemExit(f".env not found: {env_path}")

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    updated = False
    out_lines = []
    for line in lines:
        if line.strip().startswith("SYMBOLS="):
            out_lines.append(f"SYMBOLS={symbols}")
            updated = True
        else:
            out_lines.append(line)

    if not updated:
        # Добавим в конец
        if out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        out_lines.append("# Обновлено скриптом update_env_symbols.py")
        out_lines.append(f"SYMBOLS={symbols}")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"✓ Updated {env_path}")
    print(f"✓ SYMBOLS={symbols}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


