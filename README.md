# URL Shortener

Проект сервиса сокращения ссылок на FastAPI, PostgreSQL и Redis.

## Функционал

### Основной функционал

1. Авторизация
- **POST /auth/register** - Регистрация нового пользователя. Принимает username и password.
- **POST /auth/login** - Вход и получение JWT-токена. Токен используется для авторизации в защищенных эндпоинтах.


2. **Создание / удаление / изменение / получение информации по короткой ссылке:**
   - POST /links/shorten - создает короткую ссылку. Можно передать custom_alias для своей ссылки и expires_at для задания времени жизни. Если передать JWT-токен, ссылка будет привязана к пользователю.
   - GET /{short_code} - перенаправляет на оригинальный URL
   - DELETE /links/{short_code} - (требует авторизации). Удаление короткой ссылки. Доступно только создателю. 
   - PUT /links/{short_code} - обновляет оригинальный URL. Доступно только создателю ссылки.

3. **Статистика по ссылке:**
   - GET /links/{short_code}/stats - Получение статистики по ссылке: оригинальный URL, дата создания, дата последнего использования и количество переходов (кликов). Доступно только автору.

4. **Создание кастомных ссылок (уникальный alias):**
   - POST /links/shorten с передачей custom_alias
   - Проверка уникальности alias

5. **Поиск ссылки по оригинальному URL:**
   - GET /links/search?original_url={url} (требует авторизации) Поиск уже существующей короткой ссылки по оригинальному URL среди ссылок текущего пользователя.

6. **Указание времени жизни ссылки:**
   - POST /links/shorten с параметром expires_at
   - Автоматическое удаление истекших ссылок фоновой задачей

### Дополнительные функции

- **Генерация QR-кода:**
  - GET /links/{short_code}/qr - генерация QR-кода для короткой ссылки в формате PNG. 

- **Список всех ссылок пользователя:**
  - GET /links (требует авторизации) - возвращает все ссылки текущего авторизованного пользователя с пагинацией (параметры: page, per_page).


## Запуск

   Поднятие контейнеров через docker compose
   ```bash
   docker compose up -d
   ```
   При первом запуске база данных инициализируется автоматически, и создадутся нужные таблицы.

Сервис будет доступен по адресу http://{addr}:8000

### Остановка и удаление данных

```bash
docker compose down -v
```


## Описание БД

Проект использует PostgreSQL в качестве основной базы данных и Redis для кэширования.

### Структура базы данных PostgreSQL

**Таблица users:**
- id - уникальный идентификатор пользователя
- username - имя пользователя
- password_hash - хэш пароля (bcrypt)
- created_at - дата регистрации

**Таблица links:**
- short_code - короткий код ссылки
- original_url - оригинальный URL
- user_id - идентификатор пользователя-создателя (NULL для анонимных ссылок)
- clicks - количество переходов по ссылке
- expires_at - время истечения ссылки (NULL для бессрочных)
- last_used_at - дата последнего использования
- created_at - дата создания

**Индексы:**
- idx_links_user_id - индекс по user_id для быстрого поиска ссылок пользователя
- idx_links_original_url - индекс по original_url для поиска ссылок по оригинальному URL

### Кэширование в Redis

- Ключи вида **link:{short_code}** - кэш данных о ссылке (TTL: 1 час). Используется для быстрого доступа к оригинальному URL без обращения к БД при редиректах.
- Ключи вида **clicks:{short_code}** - счетчики кликов для последующей синхронизации с БД. Накопление кликов в Redis позволяет избежать частых обновлений БД при массовых переходах по ссылкам.

**Фоновые задачи:**
- Синхронизация счетчиков кликов из Redis в PostgreSQL (сейчас - каждые 60 секунд). Это обеспечивает актуальность статистики в БД без нагрузки на базу при каждом переходе.
- Автоматическая очистка истекших ссылок: удаление из БД и очистка кэша для ссылок с истекшим сроком жизни (expires_at).

## Примеры запросов (API)


### 1. Создание короткой ссылки (анонимно)
```bash
curl -X POST "http://localhost:8000/links/shorten" \
     -H "Content-Type: application/json" \
     -d '{"original_url": "https://example.com/very-long-url", "custom_alias": "myalias"}'
```

### 2. Регистрация пользователя
```bash
curl -X POST "http://localhost:8000/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "password123"}'
```

### 3. Авторизация (получение токена)
```bash
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=password123"
```
*(В ответ вернется access_token, который нужно использовать в заголовке Authorization: Bearer <token>)*

### 4. Статистика по ссылке (нужна авторизация)
```bash
curl -X GET "http://localhost:8000/links/myalias/stats" \
     -H "Authorization: Bearer ВАШ_ТОКЕН"
```

### 5. Получение QR-кода ссылки
```bash
curl -X GET "http://localhost:8000/links/myalias/qr" --output qrcode.png
```

### 6. Список всех ссылок пользователя
```bash
curl -X GET "http://localhost:8000/links?page=1&per_page=20" \
     -H "Authorization: Bearer ВАШ_ТОКЕН"
```


# Тестирование
Реализовано 100% покрытие тестами.

Тесты разделены на две категории:
- tests/unit/ - Unit-тесты
- tests/functional/ - Функциональные тесты

### Запуск тестов и проверка покрытия

```bash
# 1. Запуск сервиса
docker compose up -d

# 2. Установка зависимостей в виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock httpx locust fakeredis pytest-asyncio

# 3. Запуск тестов с проверкой покрытия
DATABASE_URL=postgresql://shortener_user:shortener_pass@localhost:5432/url_shortener \
REDIS_URL=redis://localhost:6379/0 \
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

После выполнения команды в консоли отобразится отчет о покрытии кода (100%). 
Также отчет сохранится (сохранен) в файл htmlcov/index.html.


## Coverage

coverage: platform linux, python 3.13.7-final-0

| Name                    | Stmts | Miss | Cover |
| ----------------------- | ----- | ---- | ----- |
| src/\_\_init\_\_.py     | 37    | 0    | 100%  |
| src/auth.py             | 25    | 0    | 100%  |
| src/background_tasks.py | 11    | 0    | 100%  |
| src/config.py           | 20    | 0    | 100%  |
| src/links.py            | 80    | 0    | 100%  |
| src/main.py             | 27    | 0    | 100%  |
| src/redirect.py         | 30    | 0    | 100%  |
| src/schemas.py          | 46    | 0    | 100%  |
| src/security.py         | 14    | 0    | 100%  |
| TOTAL                   | 290   | 0    | 100%  |

Coverage HTML written to dir htmlcov


### Нагрузочное тестирование (Locust)

В директории tests/ скрипт locustfile.py предназначен для тестирования массового создания ссылок и редиректов.
Запустить нагрузочное тестирование можно через web-интерфейс или в headless-режиме:

```bash
docker compose up -d

# Запуск Locust с web-интерфейсом:
source .venv/bin/activate
locust -f tests/locustfile.py --host=http://localhost:8000
```

После запуска необходимо открыть в браузере http://localhost:8089, в интерфейсе указать количество пользователей, скорость добавления и нажать "Start" для начала тестирования.

```bash
# Запуск Locust в headless режиме:
source .venv/bin/activate
locust -f tests/locustfile.py --headless -u 100 -r 10 -t 30s --host=http://localhost:8000
```

### Результаты нагрузочного тестирования

Использовался Locus для получения редиректов GET /{short_code} (кешированные запросы Redis vs PostgreSQL + Index). 100 пользователей, Ramp Up = 100. Без кеш-промахов


|                    | Name                | Requests | Fails | Median (ms) | 95%ile (ms) | 99%ile (ms) | Average (ms) | Min (ms) | Max (ms) |
| ------------------ | ------------------- | -------- | ----- | ----------- | ----------- | ----------- | ------------ | -------- | -------- |
|                    | POST /links/shorten | 100000   | 0     | 57          | 180         | 270         | 72           | 3        | 771      |
| PostgreSQL + Index | GET /[short_code]   | 153364   | 0     | 68          | 150         | 220         | 73.41        | 5        | 696      |
| Redis              | GET /[short_code]   | 150081   | 0     | 51          | 83          | 110         | 55.17        | 6        | 274      |


**Вывод:** для простейшего запроса обращение к кешу по сравнению с обращением в реляционную БД по индексу дает выигрыш в скорости, но небольшой

