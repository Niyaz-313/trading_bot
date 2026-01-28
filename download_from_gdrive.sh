#!/bin/bash
# Скрипт для скачивания файла с Google Drive
# Использование: ./download_from_gdrive.sh FILE_ID OUTPUT_FILE

FILE_ID=$1
OUTPUT_FILE=$2

if [ -z "$FILE_ID" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Использование: $0 FILE_ID OUTPUT_FILE"
    echo "Пример: $0 1fIRfqv2P--0dNT4z9tvafYnoNP0GhtLy main.py"
    exit 1
fi

echo "Скачивание файла с Google Drive..."
echo "ID файла: $FILE_ID"
echo "Выходной файл: $OUTPUT_FILE"
echo ""

# Метод 1: Простое скачивание (для небольших файлов)
echo "Попытка 1: Простое скачивание..."
curl -L "https://drive.google.com/uc?export=download&id=$FILE_ID" -o "$OUTPUT_FILE"

if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
    echo "✓ Файл успешно скачан!"
    exit 0
fi

# Метод 2: С подтверждением (для больших файлов)
echo ""
echo "Попытка 2: Скачивание с подтверждением..."
COOKIE_FILE=$(mktemp)
CONFIRM_FILE=$(mktemp)

# Получаем cookie и confirmation token
curl -c "$COOKIE_FILE" -s -L "https://drive.google.com/uc?export=download&id=$FILE_ID" > /dev/null
CONFIRM=$(curl -b "$COOKIE_FILE" -s -L "https://drive.google.com/uc?export=download&id=$FILE_ID" | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')

if [ -n "$CONFIRM" ]; then
    echo "Подтверждение получено: $CONFIRM"
    curl -Lb "$COOKIE_FILE" "https://drive.google.com/uc?export=download&confirm=$CONFIRM&id=$FILE_ID" -o "$OUTPUT_FILE"
    
    if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
        echo "✓ Файл успешно скачан!"
        rm -f "$COOKIE_FILE" "$CONFIRM_FILE"
        exit 0
    fi
fi

# Очистка
rm -f "$COOKIE_FILE" "$CONFIRM_FILE"

echo "✗ Не удалось скачать файл"
echo ""
echo "Попробуйте:"
echo "1. Убедитесь, что файл доступен для всех (Правой кнопкой → Получить ссылку → Все, у кого есть ссылка)"
echo "2. Проверьте правильность FILE_ID"
echo "3. Используйте веб-терминал для создания файла вручную"
exit 1

# Скрипт для скачивания файла с Google Drive
# Использование: ./download_from_gdrive.sh FILE_ID OUTPUT_FILE

FILE_ID=$1
OUTPUT_FILE=$2

if [ -z "$FILE_ID" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Использование: $0 FILE_ID OUTPUT_FILE"
    echo "Пример: $0 1fIRfqv2P--0dNT4z9tvafYnoNP0GhtLy main.py"
    exit 1
fi

echo "Скачивание файла с Google Drive..."
echo "ID файла: $FILE_ID"
echo "Выходной файл: $OUTPUT_FILE"
echo ""

# Метод 1: Простое скачивание (для небольших файлов)
echo "Попытка 1: Простое скачивание..."
curl -L "https://drive.google.com/uc?export=download&id=$FILE_ID" -o "$OUTPUT_FILE"

if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
    echo "✓ Файл успешно скачан!"
    exit 0
fi

# Метод 2: С подтверждением (для больших файлов)
echo ""
echo "Попытка 2: Скачивание с подтверждением..."
COOKIE_FILE=$(mktemp)
CONFIRM_FILE=$(mktemp)

# Получаем cookie и confirmation token
curl -c "$COOKIE_FILE" -s -L "https://drive.google.com/uc?export=download&id=$FILE_ID" > /dev/null
CONFIRM=$(curl -b "$COOKIE_FILE" -s -L "https://drive.google.com/uc?export=download&id=$FILE_ID" | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')

if [ -n "$CONFIRM" ]; then
    echo "Подтверждение получено: $CONFIRM"
    curl -Lb "$COOKIE_FILE" "https://drive.google.com/uc?export=download&confirm=$CONFIRM&id=$FILE_ID" -o "$OUTPUT_FILE"
    
    if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
        echo "✓ Файл успешно скачан!"
        rm -f "$COOKIE_FILE" "$CONFIRM_FILE"
        exit 0
    fi
fi

# Очистка
rm -f "$COOKIE_FILE" "$CONFIRM_FILE"

echo "✗ Не удалось скачать файл"
echo ""
echo "Попробуйте:"
echo "1. Убедитесь, что файл доступен для всех (Правой кнопкой → Получить ссылку → Все, у кого есть ссылка)"
echo "2. Проверьте правильность FILE_ID"
echo "3. Используйте веб-терминал для создания файла вручную"
exit 1

# Скрипт для скачивания файла с Google Drive
# Использование: ./download_from_gdrive.sh FILE_ID OUTPUT_FILE

FILE_ID=$1
OUTPUT_FILE=$2

if [ -z "$FILE_ID" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Использование: $0 FILE_ID OUTPUT_FILE"
    echo "Пример: $0 1fIRfqv2P--0dNT4z9tvafYnoNP0GhtLy main.py"
    exit 1
fi

echo "Скачивание файла с Google Drive..."
echo "ID файла: $FILE_ID"
echo "Выходной файл: $OUTPUT_FILE"
echo ""

# Метод 1: Простое скачивание (для небольших файлов)
echo "Попытка 1: Простое скачивание..."
curl -L "https://drive.google.com/uc?export=download&id=$FILE_ID" -o "$OUTPUT_FILE"

if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
    echo "✓ Файл успешно скачан!"
    exit 0
fi

# Метод 2: С подтверждением (для больших файлов)
echo ""
echo "Попытка 2: Скачивание с подтверждением..."
COOKIE_FILE=$(mktemp)
CONFIRM_FILE=$(mktemp)

# Получаем cookie и confirmation token
curl -c "$COOKIE_FILE" -s -L "https://drive.google.com/uc?export=download&id=$FILE_ID" > /dev/null
CONFIRM=$(curl -b "$COOKIE_FILE" -s -L "https://drive.google.com/uc?export=download&id=$FILE_ID" | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')

if [ -n "$CONFIRM" ]; then
    echo "Подтверждение получено: $CONFIRM"
    curl -Lb "$COOKIE_FILE" "https://drive.google.com/uc?export=download&confirm=$CONFIRM&id=$FILE_ID" -o "$OUTPUT_FILE"
    
    if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
        echo "✓ Файл успешно скачан!"
        rm -f "$COOKIE_FILE" "$CONFIRM_FILE"
        exit 0
    fi
fi

# Очистка
rm -f "$COOKIE_FILE" "$CONFIRM_FILE"

echo "✗ Не удалось скачать файл"
echo ""
echo "Попробуйте:"
echo "1. Убедитесь, что файл доступен для всех (Правой кнопкой → Получить ссылку → Все, у кого есть ссылка)"
echo "2. Проверьте правильность FILE_ID"
echo "3. Используйте веб-терминал для создания файла вручную"
exit 1





