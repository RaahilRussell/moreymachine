# MoreyMachine

MoreyMachine is an unofficial NBA front-office analytics engine for studying
contender roster construction and player fit.

This project is not affiliated with Daryl Morey, the Philadelphia 76ers, or the
NBA.

## Setup

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

The editable install makes `moreymachine` imports work from the repository root
while keeping reusable code under `src/moreymachine`.

Optional local settings can be placed in `.env`:

```bash
MOREYMACHINE_ENV=development
MOREYMACHINE_LOG_LEVEL=INFO
MOREYMACHINE_DATA_DIR=data
```

## Project Checks

Verify the folder structure and package imports:

```bash
python scripts/check_project.py
```

Run tests:

```bash
python -m pytest
```

Format and lint:

```bash
python -m black .
python -m ruff check .
```

## Layout

```text
src/moreymachine/   Reusable package code
data/               Local data artifacts, ignored where appropriate
notebooks/          Exploratory notebooks only
scripts/            Project maintenance scripts
tests/              Automated tests
```
