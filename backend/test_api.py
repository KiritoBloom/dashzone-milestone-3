"""End-to-end test for the DashZone Milestone 3 backend.

Run against a live database (Milestone 2 script + seed_data.sql loaded):
    .venv/bin/python test_api.py

It uses FastAPI's TestClient, logs in as each user type with the seeded
accounts, and covers the happy paths plus the failure return codes. Mutations
use freshly registered users so re-runs do not clash with the seed data.
Exits 0 when every check passes, 1 otherwise.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from main import app

SUFFIX = str(int(time.time()))[-6:]

passed, failed = [], []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name} {detail}")


def expect_envelope(name, resp, ok=True, code=0):
    body = resp.json()
    good = (
        resp.status_code == 200
        and body.get("ok") is ok
        and body.get("code") == code
        and isinstance(body.get("message"), str)
        and body["message"]
        and "data" in body
    )
    check(name, good, f"(status={resp.status_code}, body={body})")
    return body


def login_client(username, password, user_type):
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        f"/api/auth/{user_type}/login",
        json={"username": username, "password": password},
    )
    body = resp.json()
    assert body.get("ok") is True, f"login failed for {username}: {body}"
    return client


def section(title):
    print(f"\n== {title} ==")


def main():
    print("DashZone Milestone 3 backend test")
    print(f"Test suffix: {SUFFIX}")

    client = TestClient(app, raise_server_exceptions=False)

    section("health and public reads")
    r = client.get("/health")
    check("GET /health", r.status_code == 200 and r.json().get("ok") is True)
    r = client.get("/api/zones")
    if r.status_code != 200:
        print(
            "DATABASE NOT REACHABLE: /api/zones did not answer. "
            "Start SQL Server and load the Milestone 2 script + seed_data.sql, "
            "then run this test again."
        )
        return 2
    body = expect_envelope("GET /zones", r)
    if body.get("data") is not None and not body["data"]:
        print("  NOTE: /zones returned no rows; is the database seeded?")
    zones = {z["zone_name"]: z["zone_id"] for z in (body.get("data") or [])}
    zone_maadi = zones.get("Maadi", 1)

    section("auth failures")
    r = client.post(
        "/api/auth/customer/login",
        json={"username": "ahmed.salem", "password": "wrong"},
    )
    expect_envelope("wrong password -> -1", r, ok=False, code=-1)
    r = client.get("/api/customer/me")
    check(
        "unauthenticated /customer/me -> 401",
        r.status_code == 401 and r.json().get("ok") is False,
        f"(status={r.status_code})",
    )
    r = client.post(
        "/api/auth/customer/register",
        json={
            "first_name": "Test",
            "last_name": "User",
            "username": "ahmed.salem",
            "password": "Pass@999",
            "email": "dup@example.com",
            "phone": "01000000999",
            "dob": "2000-01-01",
        },
    )
    expect_envelope("duplicate username -> -2", r, ok=False, code=-2)
    r = client.post(
        "/api/auth/customer/register",
        json={
            "first_name": "Test",
            "last_name": "User",
            "username": f"badphone{SUFFIX}",
            "password": "Pass@999",
            "email": f"badphone{SUFFIX}@example.com",
            "phone": "0100000999",
            "dob": "2000-01-01",
        },
    )
    check("10-digit phone -> 422", r.status_code == 422, f"(status={r.status_code})")

    section("admin (Super Admin mona.hassan)")
    admin = login_client("mona.hassan", "Pass@001", "admin")
    expect_envelope("GET /admin/me", admin.get("/api/admin/me"))
    expect_envelope("GET /admin/dashboard", admin.get("/api/admin/dashboard"))
    expect_envelope(
        "GET /admin/pending-businesses", admin.get("/api/admin/pending-businesses")
    )
    expect_envelope(
        "GET /admin/businesses?status=Pending",
        admin.get("/api/admin/businesses", params={"status": "Pending"}),
    )
    expect_envelope("GET /admin/suspended-businesses", admin.get("/api/admin/suspended-businesses"))
    expect_envelope("GET /admin/admins", admin.get("/api/admin/admins"))
    expect_envelope("GET /admin/customers", admin.get("/api/admin/customers"))
    expect_envelope("GET /admin/vouchers", admin.get("/api/admin/vouchers"))
    expect_envelope("GET /admin/blacklisted", admin.get("/api/admin/blacklisted"))
    expect_envelope("GET /admin/market", admin.get("/api/admin/market"))
    expect_envelope(
        "GET /admin/revenue", admin.get("/api/admin/revenue")
    )
    expect_envelope(
        "GET /admin/riders/top",
        admin.get("/api/admin/riders/top"),
    )
    expect_envelope(
        "GET /admin/zones/compare?zone_id=1",
        admin.get("/api/admin/zones/compare", params={"zone_id": 1}),
    )
    # create a zone and change its fee
    zone_name = f"Test Zone {SUFFIX}"
    r = admin.post("/api/admin/zones", json={"zone_name": zone_name, "delivery_fee": 10})
    expect_envelope("POST /admin/zones", r)
    zones_now = admin.get("/api/zones").json()["data"]
    new_zone = next((z for z in zones_now if z["zone_name"] == zone_name), None)
    check("new zone appears in /zones", new_zone is not None)
    if new_zone:
        r = admin.post(
            f"/api/admin/zones/{new_zone['zone_id']}/fee", json={"new_fee": 12}
        )
        expect_envelope("POST /admin/zones/{id}/fee", r)
        r = admin.post(
            "/api/admin/zones", json={"zone_name": zone_name, "delivery_fee": 10}
        )
        expect_envelope("duplicate zone -> -2", r, ok=False, code=-2)
    # create a Zone Admin and assign them a zone
    zone_admin_user = f"zoneadmin{SUFFIX}"
    r = admin.post(
        "/api/admin/admins",
        json={
            "first_name": "Zone",
            "last_name": "Admin",
            "username": zone_admin_user,
            "password": "Pass@999",
            "email": f"{zone_admin_user}@example.com",
            "phone": "01000000998",
            "dob": "1995-05-05",
            "role": "Zone Admin",
            "zone_id": zone_maadi,
        },
    )
    expect_envelope("POST /admin/admins (Zone Admin)", r)
    new_admin_id = r.json()["data"]["admin_id"]
    r = admin.post(
        f"/api/admin/admins/{new_admin_id}/assign-zone",
        json={"zone_id": zone_maadi},
    )
    expect_envelope("POST /admin/admins/{id}/assign-zone", r)

    section("admin (Zone Admin karim.adel) — Super Admin-only actions")
    zone_admin = login_client("karim.adel", "Pass@002", "admin")
    r = zone_admin.post(
        "/api/admin/zones", json={"zone_name": f"Forbidden {SUFFIX}", "delivery_fee": 5}
    )
    expect_envelope("Zone Admin create zone -> -3", r, ok=False, code=-3)
    r = zone_admin.post("/api/admin/businesses/1/suspend", json={"reason": "test"})
    expect_envelope("Zone Admin suspend -> -3", r, ok=False, code=-3)

    section("partner (tarek.fouad, business 1)")
    partner = login_client("tarek.fouad", "Pass@004", "partner")
    body = expect_envelope("GET /partner/business", partner.get("/api/partner/business"))
    check(
        "partner business is Koshary El Tahrir",
        body["data"] and body["data"].get("business_name") == "Koshary El Tahrir",
    )
    body = expect_envelope("GET /partner/products", partner.get("/api/partner/products"))
    check("partner has products", len(body.get("data") or []) >= 1)
    product_name = f"Test Koshary {SUFFIX}"
    r = partner.post(
        "/api/partner/products",
        json={
            "name": product_name,
            "description": "test product",
            "category": "Main Dishes",
            "price": 55,
            "is_available": True,
        },
    )
    expect_envelope("POST /partner/products", r)
    products = partner.get("/api/partner/products").json()["data"]
    new_product = next((p for p in products if p["product_name"] == product_name), None)
    check("new product appears", new_product is not None)
    if new_product:
        pid = new_product["product_id"]
        r = partner.post(
            f"/api/partner/products/{pid}/promotion", json={"discount_amount": 10}
        )
        expect_envelope("POST /partner/products/{id}/promotion", r)
        r = partner.post(
            f"/api/partner/products/{pid}/promotion", json={"discount_amount": 9999}
        )
        expect_envelope("discount over half price -> -1", r, ok=False, code=-1)
        r = partner.post(
            f"/api/partner/products/{pid}/toggle", json={"is_available": False}
        )
        expect_envelope("POST /partner/products/{id}/toggle off", r)
        r = partner.post(
            f"/api/partner/products/{pid}/toggle", json={"is_available": True}
        )
        expect_envelope("POST /partner/products/{id}/toggle on", r)
        r = partner.post(
            f"/api/partner/products/{pid}",
            json={
                "name": product_name,
                "description": "test product updated",
                "category": "Main Dishes",
                "price": 60,
                "is_available": True,
            },
        )
        expect_envelope("POST /partner/products/{id} (update)", r)
    expect_envelope(
        "GET /partner/performance", partner.get("/api/partner/performance")
    )

    section("partner registers a new business, admin approves it")
    partner_user = f"newpartner{SUFFIX}"
    r = client.post(
        "/api/auth/partner/register",
        json={
            "first_name": "New",
            "last_name": "Partner",
            "username": partner_user,
            "password": "Pass@999",
            "email": f"{partner_user}@example.com",
            "phone": "01000000997",
            "dob": "1990-01-01",
        },
    )
    expect_envelope("register new partner", r)
    new_partner = login_client(partner_user, "Pass@999", "partner")
    r = new_partner.post(
        "/api/partner/business",
        json={
            "name": f"Test Eats {SUFFIX}",
            "description": "test business",
            "link_website": None,
            "zone_id": zone_maadi,
            "opening_hour": "00:00",
            "closing_hour": "00:00",
            "expected_delivery_time": 30,
            "phone": "01000000996",
            "business_type": "Restaurant",
            "cuisine_type": "Egyptian",
            "food_category": "Main Dishes",
            "pharmacy_type": None,
        },
    )
    expect_envelope("POST /partner/business (new)", r)
    business_id = r.json()["data"]["business_id"]
    r = admin.post(f"/api/admin/businesses/{business_id}/approve")
    expect_envelope("POST /admin/businesses/{id}/approve", r)
    r = admin.post(f"/api/admin/businesses/{business_id}/approve")
    expect_envelope("approve again -> -4", r, ok=False, code=-4)
    r = admin.post(
        f"/api/admin/businesses/{business_id}/suspend", json={"reason": "test suspension"}
    )
    expect_envelope("POST /admin/businesses/{id}/suspend", r)
    r = admin.post(f"/api/admin/businesses/{business_id}/reinstate")
    expect_envelope("POST /admin/businesses/{id}/reinstate", r)

    section("customer: register, addresses, cards")
    customer_user = f"newcustomer{SUFFIX}"
    r = client.post(
        "/api/auth/customer/register",
        json={
            "first_name": "New",
            "last_name": "Customer",
            "username": customer_user,
            "password": "Pass@999",
            "email": f"{customer_user}@example.com",
            "phone": "01000000995",
            "dob": "2000-01-01",
        },
    )
    expect_envelope("register new customer", r)
    customer_id = r.json()["data"]["user_id"]
    customer = login_client(customer_user, "Pass@999", "customer")
    expect_envelope("GET /customer/me", customer.get("/api/customer/me"))
    r = customer.post(
        "/api/customer/addresses",
        json={"description": "Test Street 1", "zone_id": zone_maadi},
    )
    expect_envelope("POST /customer/addresses", r)
    address_id = r.json()["data"][0]["address_id"]
    r = customer.post(
        f"/api/customer/addresses/{address_id}/activate"
    )
    expect_envelope("POST /customer/addresses/{id}/activate", r)
    r = customer.post(
        "/api/customer/cards",
        json={
            "card_no": "4111111111111111",
            "card_holder_name": "New Customer",
            "expiration_date": "2030-12-31",
        },
    )
    expect_envelope("POST /customer/cards", r)
    body = expect_envelope("GET /customer/cards", customer.get("/api/customer/cards"))
    check(
        "card shows last 4 digits only",
        body["data"] and body["data"][0].get("last_four_digits") == "1111",
    )
    card_id = body["data"][0]["card_id"]
    r = customer.post(
        "/api/customer/cards",
        json={
            "card_no": "4111111111111111",
            "card_holder_name": "New Customer",
            "expiration_date": "2030-12-31",
        },
    )
    expect_envelope("duplicate card -> -2", r, ok=False, code=-2)

    section("customer: cart, checkout, cancel, reorder")
    r = customer.post("/api/customer/checkout/preview", json={})
    expect_envelope("checkout preview with empty cart -> -9", r, ok=False, code=-9)
    r = customer.post("/api/customer/cart")
    expect_envelope("POST /customer/cart", r)
    r = customer.post("/api/customer/cart")
    expect_envelope("create cart again -> -2", r, ok=False, code=-2)
    r = customer.post(
        "/api/customer/cart/items",
        json={"product_id": 1, "quantity": 11, "notes": None},
    )
    expect_envelope("quantity 11 -> -6", r, ok=False, code=-6)
    r = customer.post(
        "/api/customer/cart/items",
        json={"product_id": 11, "quantity": 1, "notes": None},
    )
    expect_envelope("product from another zone -> -5", r, ok=False, code=-5)
    r = customer.post(
        "/api/customer/cart/items",
        json={"product_id": 1, "quantity": 2, "notes": "extra spicy"},
    )
    expect_envelope("POST /customer/cart/items", r)
    r = customer.post("/api/customer/checkout/preview", json={})
    body = expect_envelope("POST /customer/checkout/preview", r)
    check(
        "preview total = subtotal + fees",
        body["data"]
        and abs(body["data"]["total"] - (body["data"]["subtotal"] + body["data"]["delivery_fees"])) < 0.01,
    )
    # admin issues a voucher to the new customer, then use it
    r = admin.post(
        "/api/admin/vouchers",
        json={
            "customer_id": customer_id,
            "promo_code": f"TEST{SUFFIX}",
            "is_percentage": False,
            "amount": 20,
            "expiry_date": "2030-12-31",
        },
    )
    expect_envelope("POST /admin/vouchers", r)
    vouchers = customer.get("/api/customer/vouchers").json()["data"]
    voucher = next((v for v in vouchers if v["promo_code"] == f"TEST{SUFFIX}"), None)
    check("issued voucher appears for the customer", voucher is not None)
    r = customer.post(
        "/api/customer/checkout/preview",
        json={"voucher_id": voucher["voucher_id"] if voucher else None},
    )
    body = expect_envelope("preview with voucher", r)
    check(
        "voucher discount applied",
        body["data"] and body["data"]["discount"] == 20,
    )
    r = customer.post(
        "/api/customer/checkout",
        json={
            "voucher_id": voucher["voucher_id"] if voucher else None,
            "payment_method": "Cash",
            "card_id": None,
        },
    )
    body = expect_envelope("POST /customer/checkout (Cash)", r)
    order_id = body["data"]["order_id"] if body.get("data") else None
    check("checkout returned an order", order_id is not None)
    rider_order_id = None
    if order_id:
        r = customer.post(f"/api/customer/orders/{order_id}/cancel")
        body = expect_envelope("POST /customer/orders/{id}/cancel", r)
        check(
            "cancel returned a refund amount",
            body["data"] and body["data"].get("refund_amount") is not None,
        )
        r = customer.post(f"/api/customer/orders/{order_id}/cancel")
        expect_envelope("cancel again -> -4", r, ok=False, code=-4)
        r = customer.post(
            f"/api/customer/orders/{order_id}/reorder",
            json={"address_id": address_id},
        )
        expect_envelope("POST /customer/orders/{id}/reorder", r)
        # The order above is now cancelled, so its delivery is no longer
        # active. Check out the reordered cart to make a second order that
        # stays open, so the rider section has a live delivery to find.
        r = customer.post(
            "/api/customer/checkout",
            json={"voucher_id": None, "payment_method": "Cash", "card_id": None},
        )
        body = expect_envelope("POST /customer/checkout (second order)", r)
        rider_order_id = body["data"]["order_id"] if body.get("data") else None
        check("second checkout returned an order", rider_order_id is not None)

    section("customer: browsing, favorites, orders")
    expect_envelope(
        "GET /customer/businesses/search",
        customer.get("/api/customer/businesses/search", params={"keyword": "Koshary"}),
    )
    expect_envelope(
        "GET /customer/businesses/category",
        customer.get(
            "/api/customer/businesses/category",
            params={"category": "Pizza", "address_id": address_id},
        ),
    )
    expect_envelope(
        "GET /customer/businesses/1", customer.get("/api/customer/businesses/1")
    )
    r = customer.get("/api/customer/businesses/99999")
    expect_envelope("unknown business -> -1", r, ok=False, code=-1)
    expect_envelope("GET /customer/favorites", customer.get("/api/customer/favorites"))
    expect_envelope(
        "GET /customer/recommended", customer.get("/api/customer/recommended")
    )
    r = customer.post(
        "/api/customer/favorites/toggle",
        json={"item_id": 1, "item_type": "Product"},
    )
    body = expect_envelope("POST /customer/favorites/toggle", r)
    check(
        "toggle returned the new state",
        body["data"] and body["data"].get("favorited") in (True, False),
    )
    expect_envelope("GET /customer/orders", customer.get("/api/customer/orders"))
    expect_envelope("GET /customer/vouchers", customer.get("/api/customer/vouchers"))
    expect_envelope("GET /customer/cart", customer.get("/api/customer/cart"))

    section("rider: availability, deliveries, earnings")
    rider = login_client("ali.ibrahim", "Pass@012", "rider")
    expect_envelope("GET /rider/me", rider.get("/api/rider/me"))
    r = rider.post("/api/rider/availability", json={"is_available": True})
    expect_envelope("POST /rider/availability", r)
    expect_envelope("GET /rider/earnings", rider.get("/api/rider/earnings"))
    expect_envelope("GET /rider/rating", rider.get("/api/rider/rating"))
    expect_envelope("GET /rider/history", rider.get("/api/rider/history"))
    # find the delivery created by the second checkout above, across the seed riders
    delivery_id = None
    suborder_id = None
    if rider_order_id:
        orders = customer.get("/api/customer/orders").json()["data"]
        order = next((o for o in orders if o["order_id"] == rider_order_id), None)
        if order and order.get("suborders"):
            sub = order["suborders"][0]
            delivery_id = sub.get("delivery_id")
            suborder_id = sub.get("suborder_id")
    rider_client = None
    if delivery_id:
        for user, pw in [
            ("ali.ibrahim", "Pass@012"),
            ("mostafa.kamal", "Pass@013"),
            ("yehia.saad", "Pass@014"),
            ("ziad.nabil", "Pass@015"),
            ("fady.ramzy", "Pass@016"),
        ]:
            c = login_client(user, pw, "rider")
            mine = c.get("/api/rider/deliveries").json()["data"]
            if any(d["delivery_id"] == delivery_id for d in mine):
                rider_client = c
                break
        check("delivery assigned to a rider", rider_client is not None)
        if rider_client:
            r = rider_client.post(f"/api/rider/deliveries/{delivery_id}/pickup")
            expect_envelope("POST /rider/deliveries/{id}/pickup", r)
            r = rider_client.post(f"/api/rider/deliveries/{delivery_id}/deliver")
            expect_envelope("POST /rider/deliveries/{id}/deliver", r)
            if suborder_id:
                r = customer.post(
                    f"/api/customer/orders/suborders/{suborder_id}/feedback",
                    json={
                        "headline": "Great food",
                        "description": "Arrived hot and fast.",
                        "rating": 5,
                    },
                )
                expect_envelope("POST .../feedback", r)
                r = customer.post(
                    f"/api/customer/orders/suborders/{suborder_id}/rate-rider",
                    json={"rider_rating": 5},
                )
                expect_envelope("POST .../rate-rider", r)
    else:
        print("  NOTE: no delivery found for the test order; skipping rider pickup/deliver.")

    section("admin: blacklist and lift")
    r = admin.post(
        f"/api/admin/customers/{customer_id}/blacklist",
        json={"reason": "test blacklist"},
    )
    expect_envelope("POST /admin/customers/{id}/blacklist", r)
    r = admin.post(
        f"/api/admin/customers/{customer_id}/blacklist",
        json={"reason": "test blacklist again"},
    )
    expect_envelope("blacklist again -> -4", r, ok=False, code=-4)
    r = admin.post(f"/api/admin/customers/{customer_id}/lift-blacklist")
    expect_envelope("POST /admin/customers/{id}/lift-blacklist", r)

    section("cross-type access")
    r = customer.get("/api/admin/dashboard")
    check(
        "customer hitting admin endpoint -> 403",
        r.status_code == 403 and r.json().get("ok") is False,
        f"(status={r.status_code})",
    )
    r = partner.get("/api/customer/orders")
    check(
        "partner hitting customer endpoint -> 403",
        r.status_code == 403 and r.json().get("ok") is False,
        f"(status={r.status_code})",
    )
    r = client.post("/api/auth/logout")
    expect_envelope("POST /auth/logout", r)

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("Failed checks:")
        for name in failed:
            print(f"  - {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
