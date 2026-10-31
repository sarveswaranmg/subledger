# SubLedger — Django REST Framework + PostgreSQL

A learning-focused billing backend implementing plans, customers, subscriptions, invoices, payment attempts, and append-only ledger events.

## Requirements
- Python 3.12+
- PostgreSQL 14+ (or Docker Desktop)

## Quick start with Docker (recommended)
```bash
docker compose up --build
```
API: `http://localhost:8000/api/`

## Local setup
1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Create PostgreSQL database and user, then copy `.env.example` to `.env`. Export the variables from `.env` in your shell (or configure them in your IDE).
3. Generate and apply migrations:
   ```bash
   python manage.py makemigrations billing
   python manage.py migrate
   python manage.py runserver
   ```
4. Open `http://127.0.0.1:8000/api/`.

## Suggested API walkthrough
1. `POST /api/plans/` with `{"name":"Starter","description":"Entry plan","price":"499.00","currency":"INR","billing_cycle":"monthly","is_active":true}`
2. `POST /api/customers/` with `{"name":"Test Customer","email":"test@example.com","status":"active"}`
3. `POST /api/subscriptions/` with `{"customer":"CUSTOMER_UUID","plan":"PLAN_UUID","status":"active"}`
4. `POST /api/invoices/generate/` with `{"subscription_id":"SUBSCRIPTION_UUID"}`
5. `POST /api/invoices/INVOICE_UUID/payments/` with `{"amount":"200.00","currency":"INR","status":"succeeded","provider_reference":"provider-ref-001"}`
6. `GET /api/customers/CUSTOMER_UUID/ledger/`

Use UUIDs returned by each preceding response. A failed payment can be recorded with `status: "failed"` and optional `failure_reason`.

## Tests
```bash
python manage.py test billing.tests
```
Tests cover positive plan price, inactive plan, duplicate active subscription, invoice price snapshot and ledger event, overpayment rejection, partial/full payment state changes, and failed-payment balance invariance.

## Design
See [DESIGN.md](DESIGN.md) for ERD, model responsibilities, business rule ownership, service flows, APIs, patterns, assumptions, and limitations.

## Notes
This project records payment outcomes; it does not charge real payment methods. Authentication is intentionally omitted for assignment simplicity. Add proper permissions and secrets management before deployment.
