# Структура тестов

Тесты разделены на две категории:

## `unit/` - Unit-тесты

Тестируют отдельные функции и методы в изоляции, без использования HTTP API.

- `test_auth.py` - тестирует функции `_decode_token`, `get_current_user_id`, `get_optional_user_id` напрямую
- `test_background.py` - тестирует функцию `run_background_tasks` напрямую

## `functional/` - Функциональные тесты

Тестируют API через HTTP-клиент (`AsyncClient`), проверяя полный flow работы системы.

- `test_auth.py` - тестирует endpoints `/auth/register`, `/auth/login`
- `test_links.py` - тестирует endpoints для работы со ссылками
- `test_links_management.py` - тестирует CRUD операции со ссылками
- `test_main.py` - тестирует root endpoint
- `test_qr.py` - тестирует генерацию QR-кодов

## Запуск тестов

```bash
# Все тесты
pytest tests/

# Только unit-тесты
pytest tests/unit/

# Только функциональные тесты
pytest tests/functional/

# С покрытием
pytest tests/ --cov=src --cov-report=html
```
