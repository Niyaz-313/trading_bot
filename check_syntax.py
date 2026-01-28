#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка синтаксиса main.py"""

import ast
import sys

try:
    with open('main.py', 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print("✅ Синтаксис корректен!")
    sys.exit(0)
except SyntaxError as e:
    print(f"❌ Синтаксическая ошибка: {e}")
    print(f"   Строка {e.lineno}: {e.text}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sys.exit(1)



