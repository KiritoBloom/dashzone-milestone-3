# Backend — DashZone Milestone 3

FastAPI app for the DashZone web app (Data Base I, Winter 2026, Team 117).
Owned by Mohamed. This is the foundation the whole team builds on: every
page calls this API, and this API calls only the Milestone 2 procedures,
functions and views in the SQL Server database. It never writes to the
tables directly and never rewrites the Milestone 2 business logic.

## Quick start

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DB_PASSWORD to the SQL Server SA password,
# and SESSION_SECRET to a long random string.
.venv/bin/python -m uvicorn main:app --port 8000 --reload
```

The API is at `http://localhost:8000/api`. Check it is up:

```bash
curl http://localhost:8000/health
```

When the database is up it answers `{"ok": true, ... "database": "ok"}`.
When the database is down it answers HTTP 503 with `"database": "down"`.

Test login (seed data): Super Admin, username `mona.hassan`, password `Pass@001`.

## How it works

- **Sessions.** Signed cookies (Starlette `SessionMiddleware`) holding
  `user_id` and `user_type`. The frontend never sends a user ID; every
  endpoint reads it from the session. Log in once, the cookie follows.
- **One envelope.** Every endpoint returns the same shape:
  `{"ok": bool, "code": int, "message": str, "data": ...}`. `ok` is true
  exactly when `code` is 0. `code` is the Milestone 2 procedure's return
  code (0 to -9, Table 3.1 in the milestone doc). The message is always in
  the user's words and says how to fix the problem. A raw SQL error or a
  bare error code is never returned.
- **Validation before the database.** Pydantic models reject bad input with
  a clear message before any procedure runs: required fields, numbers,
  dates, 11-digit phone numbers, 16-digit card numbers. Passwords are
  never returned in any response.
- **Ownership.** A user only ever sees and changes their own records. The
  IDs in a URL are the record being acted on, never the signed-in user.
  A rider can only pick up a delivery assigned to them; a partner can only
  change their own products; a customer can only touch their own addresses,
  cards, cart and orders.
- **Super Admin only.** The backend checks `h_IsSuperAdmin` itself for
  creating an admin, assigning a zone, suspending or reinstating a
  business, creating a zone and changing a zone fee. A Zone Admin trying
  one of these gets code -3. (The SQL lets a Zone Admin suspend a business
  in their own zone; the milestone doc says Super Admin only, so the
  backend enforces the doc.)

## Files

| File | What it does |
| --- | --- |
| `main.py` | App, session + CORS middleware, the two error handlers (401/403 auth, 500 database), `GET /health`, router wiring. |
| `db.py` | The only place that talks to SQL Server. `call_proc` (the `DECLARE @rc` pattern, collects extra result sets), `call_scalar`, `call_table_func`, `query_view`, `ping` for `/health`, row serialisation (dates to ISO, Decimal to float). Never leaks a raw SQL error. |
| `auth.py` | Session helpers: `get_current_user`, `require_type` (the per-router role check), `is_super_admin`, the login flow (validation function, then `h_GetUserId`), `profile_for`. |
| `messages.py` | The response envelope and the Table 3.1 messages in the user's words. `proc_reply` turns a procedure's return code into a reply. |
| `models.py` | Pydantic request models and their rules (phone, card, restaurant vs pharmacy, Zone Admin vs Super Admin, card only when paying by Card). |
| `routers/auth.py` | Register, login, logout, `/auth/me` for all four user types. Admins only log in. |
| `routers/shared.py` | `GET /zones`, the zone list every registration and address form needs. No sign-in required. |
| `routers/admin.py` | Admin (Adham): approvals, suspend/reinstate, admins and zones, vouchers, blacklist, dashboard, revenue, riders, market. |
| `routers/partner.py` | Partner (Karim): my business, products, promotions, performance. |
| `routers/rider.py` | Rider (Adam): profile, availability, active deliveries, pickup/deliver, earnings, rating, history. |
| `routers/customer.py` | Customer (Eyad): profile, addresses, cards, cart, checkout preview and checkout, browsing, favorites, orders, cancel/reorder, feedback, rate rider. |
| `routers/common.py` | Helpers shared by the routers (the default 30-day report window). |
| `test_api.py` | End-to-end test, see below. |
| `requirements.txt` | Pinned dependencies (exact versions). |
| `requirements-lock.txt` | Full transitive lock (`pip freeze`) for an exact reproduction. |
| `.env.example` | Every setting, with the local defaults. Copy to `.env` and fill in the secrets. Never commit `.env`. |

## Configuration

All settings are environment variables, loaded from `.env` if it exists
(`python-dotenv`). The defaults are the local ones.

| Variable | Default | What it is |
| --- | --- | --- |
| `DB_SERVER` | `localhost` | SQL Server host. |
| `DB_NAME` | `LocalDeliveryMarketplace_Team_00` | The CMS database. |
| `DB_USER` | `sa` | SQL Server login. |
| `DB_PASSWORD` | (empty) | The SA password. Required; without it every database call fails. |
| `DB_DRIVER` | `ODBC Driver 18 for SQL Server` | The ODBC driver. |
| `SESSION_SECRET` | built-in dev secret | Signs the session cookie. Change it to a long random string before sharing the server; a warning is logged while the default is in use. |

## Database

Run the CMS script, then the seed data, in SQL Server (both in `../sql/`):

```bash
sqlcmd -S localhost -U sa -P <password> -C -i ../sql/MS3_Database_Solution.sql
sqlcmd -S localhost -U sa -P <password> -C -i ../sql/seed_data.sql
```

That creates `LocalDeliveryMarketplace_Team_00` with 25 tables, 48
procedures, 42 functions and 13 views, plus the seed data (24 users, 4
zones, 8 businesses, 20 products). The seed Super Admin is `mona.hassan` /
`Pass@001`.

On this VM, SQL Server lives outside the home directory, so a VM
replacement wipes it. `../sql/reinstall-sqlserver.sh` reinstalls it and
reuses the saved SA password.

## Test

```bash
.venv/bin/python test_api.py
```

This exercises every endpoint against the live database (it must be up,
with the script and seed data loaded). It logs in as each user type and
covers the happy paths and the failure return codes: wrong password,
duplicate username, duplicate card, blacklisted customer, a product from
another zone, quantity over 10, cancelling twice, and the cross-type 403s.
It reads the database connection from `.env` (or from the `DB_*`
environment variables if those are set). Mutations use freshly registered
users so re-runs do not clash with the seed data. Exits 0 when every
check passes. Last run: 100 passed, 0 failed.

## API contract

`../docs/api-contract.md` maps every endpoint to its Milestone 2
procedure, function or view, with the request body and response shape.
Where the contract and the SQL differ, the SQL wins and the difference is
noted in the contract and in the router's docstring:

- `Calculate_Voucher_Discount` needs the order subtotal as well as the
  voucher ID, so the checkout preview computes the subtotal from the cart.
- `Checkout_Cart` and `Cancel_Order` return only a return code, so the
  new order is looked up in `My_Order_History` after checkout, and the
  refund is read from there before cancelling.
- `Reorder` creates a cart, not an order; the endpoint returns that cart.
- `Toggle_Favorite` does not report the new state; for products it is
  read back from `My_Favorites` (there is no helper listing favorite
  businesses, so those return `favorited: null`).
- `h_MyActiveCart` and `h_GetUserId` are scalar functions returning an ID
  or NULL, not table functions.
- Order ETAs use `order_date + (expected_delivery_time + zone average
  tracking time)` minutes per suborder, and the order ETA is the latest
  of its suborders.
