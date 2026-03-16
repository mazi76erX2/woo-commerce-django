# Woo Commerce Django

Super simple local setup.

## Requirements

- Python 3.14+
- Docker + Docker Compose

## 1) Start WordPress + MySQL (Docker)

```bash
docker compose up -d
```

Open `http://localhost:8080` and complete the WordPress install wizard.

## 2) Install WooCommerce in WordPress

In WordPress admin:

- Go to `Plugins` → `Add New`
- Search for `WooCommerce`
- Install and activate it

## 3) Change permalinks (required)

In WordPress admin:

- Go to `Settings` → `Permalinks`
- Select `Post name`
- Click `Save Changes`

## 4) Create WooCommerce API keys

In WordPress admin:

- Go to `WooCommerce` → `Settings` → `Advanced` → `REST API`
- Click `Add key`
- Permission: `Read`
- Copy the `Consumer key` and `Consumer secret`

## 5) Install Django app

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 6) Environment

Create a `.env` file in the project root:

```env
SECRET_KEY=dev-secret-key
WOO_API_URL=http://localhost:8080/wp-json/wc/v3

# Used by Django settings
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# Used by current assessment view
WOO_KEY=ck_xxx
WOO_SECRET=cs_xxx

# Used by WooCommerce webhook verification
WOO_WEBHOOK_SECRET=your_webhook_secret

# ClickUp sync
CLICKUP_TOKEN=pk_xxx
CLICKUP_LIST_ID=123456789012
# You can also paste the full list URL; the app will extract the list ID
# CLICKUP_LIST_ID=https://app.clickup.com/90152473472/v/l/2kyr34w0-455?pr=901510547731
# Optional (defaults to https://api.clickup.com/api/v2)
# CLICKUP_API_URL=https://api.clickup.com/api/v2
# Optional: only set this if your list has a matching status name
# CLICKUP_TASK_STATUS=to do
```

## 7) Run Django

```bash
python manage.py migrate
python manage.py runserver
```

API endpoint:

- `GET http://127.0.0.1:8000/api/orders/today/`

## 8) WooCommerce → ClickUp sync setup

Create DB tables:

```bash
python manage.py migrate
```

In WordPress admin, create a WooCommerce webhook:

- Go to `WooCommerce` → `Settings` → `Advanced` → `Webhooks`
- Click `Add webhook`
- Topic: `Order created` (optionally add another for `Order updated`)
- Delivery URL: `http://host.docker.internal:8000/api/orders/webhook/woocommerce/`
- Secret: use the same value as `WOO_WEBHOOK_SECRET` in `.env`
- Status: `Active`

How it works:

- WooCommerce sends order payload to your webhook endpoint
- Django verifies signature (`X-WC-Webhook-Signature`)
- A ClickUp task is created for first sync, then updated for later changes
- Duplicate webhook deliveries are ignored after processing
