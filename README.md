# Woo Commerce Django

Super simple local setup.

## Requirements

- Python 3.14+

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment

Create a `.env` file in the project root:

```env
SECRET_KEY=dev-secret-key
WOO_API_URL=https://your-store.com/wp-json/wc/v3
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx
```

## Run

```bash
python manage.py migrate
python manage.py runserver
```

API endpoint:

- `GET http://127.0.0.1:8000/api/orders/today/`
