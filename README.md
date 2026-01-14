# 🏃 Дневник пробежек

CLI для ведения беговых тренировок: добавление пробежек, недельные/месячные сводки, рекорды и сравнение прогресса.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Альтернатива через Makefile:

```bash
make install
```

## Команды

```bash
./run add 5.2km 27:30
./run add 10km 58:45 --note "последние 2км умирал"
./run add 800m 3:20
./run add 5,2 27:30
RUN_UNIT=mi ./run add 3.1 27:30
./run --no-style week
./run --no-color week
./run week
./run month
./run best 5km
./run progress
./run compare --weeks 4
```

## Тесты (BDD)

```bash
python -m pytest
```

Или:

```bash
make test
```

## Хранилище данных

По умолчанию данные сохраняются в `runs.db` в текущей директории.
Для тестов и отладки можно указать путь через переменную окружения:

```bash
RUN_DB=/tmp/runs.db ./run week
```

## Переменные окружения

- `RUN_DB` — путь к SQLite базе.
- `RUN_TODAY` — дата "сегодня" в формате `YYYY-MM-DD` (полезно для тестов).
- `RUN_UNIT` — единицы расстояния по умолчанию: `km` или `mi` (по умолчанию `km`).

## Стиль вывода

По умолчанию при запуске в терминале включены цвет и эмодзи. Отключить можно флагами:
- `--no-style` — без цвета и эмодзи.
- `--no-color` — без цвета (эмодзи остаются).
