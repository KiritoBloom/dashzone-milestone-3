"""Customer endpoints (Eyad).

The customer is the signed-in customer. No customer ID in the request; it
comes from the session. The cart is the active cart of the active address.

Two places where the contract and the SQL differ, handled here:
- Calculate_Voucher_Discount needs the order subtotal as well as the voucher
  ID, so the checkout preview computes the subtotal from the cart first.
- Checkout_Cart and Cancel_Order return only a return code, so after a
  successful checkout the new order is looked up in My_Order_History, and
  before cancelling the refund is read from My_Order_History
  (total_amount minus refunded_amount).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query

import auth
import db
from messages import fail, ok, proc_reply
from models import (
    AddToCartBody,
    AddressBody,
    CardBody,
    CheckoutBody,
    CheckoutPreviewBody,
    FavoriteBody,
    FeedbackBody,
    RateRiderBody,
    ReorderBody,
    UpdateAddressBody,
)

router = APIRouter(tags=["customer"])
customer_only = Depends(auth.require_type("customer"))


# ---------------------------------------------------------------- helpers

def _active_cart_id(customer_id: int):
    cart_id = db.call_scalar("h_MyActiveCart", (customer_id,))
    return int(cart_id) if cart_id is not None else None


def _cart_items(cart_id: int):
    return db.call_table_func("h_CartItems", (cart_id,))


def _cart_data(customer_id: int):
    """(cart_id, items) for the active cart, or (None, []) when there is none."""
    cart_id = _active_cart_id(customer_id)
    if cart_id is None:
        return None, []
    return cart_id, _cart_items(cart_id)


def _addresses(customer_id: int):
    return db.call_table_func("h_MyAddresses", (customer_id,))


def _owns_address(customer_id: int, address_id: int) -> bool:
    return any(a["address_id"] == address_id for a in _addresses(customer_id))


def _my_orders(customer_id: int):
    return db.call_table_func("My_Order_History", (customer_id,))


def _owns_order(customer_id: int, order_id: int):
    orders = _my_orders(customer_id)
    return next((o for o in orders if o["order_id"] == order_id), None)


def _owns_suborder(customer_id: int, suborder_id: int) -> bool:
    for order in _my_orders(customer_id):
        subs = db.call_table_func("h_OrderSubOrders", (order["order_id"],))
        if any(s["suborder_id"] == suborder_id for s in subs):
            return True
    return False


# ---------------------------------------------------------------- profile

@router.get("/customer/me")
def customer_me(user=customer_only):
    rows = db.call_table_func("h_CustomerProfile", (user["user_id"],))
    if not rows:
        return fail(-1, "Customer profile not found.")
    return ok(rows[0], "Your profile loaded.")


# ---------------------------------------------------------------- addresses

@router.get("/customer/addresses")
def my_addresses(user=customer_only):
    return ok(_addresses(user["user_id"]), "Your addresses loaded.")


@router.post("/customer/addresses")
def add_address(body: AddressBody, user=customer_only):
    rc, _ = db.call_proc(
        "Add_Customer_Address", (user["user_id"], body.description, body.zone_id)
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The address was added.",
            failure_messages={
                -1: "The address details are not valid. Please check them and try again.",
            },
        )
    return ok(_addresses(user["user_id"]), "The address was added.")


@router.post("/customer/addresses/{address_id}")
def update_address(address_id: int, body: UpdateAddressBody, user=customer_only):
    rc, _ = db.call_proc(
        "Update_Delete_Customer_Address",
        (
            user["user_id"],
            address_id,
            body.description,
            body.zone_id,
            body.action,
        ),
    )
    if rc != 0:
        verb = "updated" if body.action == "Update" else "deleted"
        return proc_reply(
            rc,
            f"The address was {verb}.",
            failure_messages={
                -1: "This address does not exist, or the details are not valid.",
                -3: "This address is not yours.",
                -4: "This address cannot be changed because it has an order on the way, "
                    "or a cart uses it.",
            },
        )
    verb = "updated" if body.action == "Update" else "deleted"
    return ok(_addresses(user["user_id"]), f"The address was {verb}.")


@router.post("/customer/addresses/{address_id}/activate")
def activate_address(address_id: int, user=customer_only):
    rc, _ = db.call_proc(
        "Change_Active_Address", (user["user_id"], address_id)
    )
    if rc != 0:
        return proc_reply(
            rc,
            "This is your active address now.",
            failure_messages={-3: "This address is not yours."},
        )
    return ok(_addresses(user["user_id"]), "This is your active address now.")


# ---------------------------------------------------------------- cards

@router.get("/customer/cards")
def my_cards(user=customer_only):
    return ok(
        db.call_table_func("h_MyCards", (user["user_id"],)),
        "Your cards loaded.",
    )


@router.post("/customer/cards")
def add_card(body: CardBody, user=customer_only):
    rc, _ = db.call_proc(
        "Add_Card",
        (
            user["user_id"],
            body.card_no,
            body.card_holder_name,
            body.expiration_date,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The card was saved.",
            failure_messages={
                -1: "The card details are not valid. Check the number, the name and the expiry date.",
                -2: "This card is already saved.",
            },
        )
    return ok(
        db.call_table_func("h_MyCards", (user["user_id"],)),
        "The card was saved.",
    )


# ---------------------------------------------------------------- cart

@router.get("/customer/cart")
def my_cart(user=customer_only):
    cart_id, items = _cart_data(user["user_id"])
    if cart_id is None:
        return ok({"cart_id": None, "items": []}, "You do not have an active cart.")
    return ok({"cart_id": cart_id, "items": items}, "Your cart loaded.")


@router.post("/customer/cart")
def create_cart(user=customer_only):
    rc, _ = db.call_proc("Create_Cart", (user["user_id"],))
    cart_id, items = _cart_data(user["user_id"])
    if rc != 0:
        return proc_reply(
            rc,
            "Your cart was created.",
            data={"cart_id": cart_id, "items": items},
            failure_messages={
                -1: "You do not have an active address. Add one first.",
                -2: "You already have an active cart.",
                -3: "Your account is blacklisted, so you cannot shop. Contact support.",
            },
        )
    return ok({"cart_id": cart_id, "items": items}, "Your cart was created.")


@router.post("/customer/cart/items")
def add_to_cart(body: AddToCartBody, user=customer_only):
    cart_id = _active_cart_id(user["user_id"])
    if cart_id is None:
        return fail(-9, "You do not have an active cart. Create one first.")
    rc, _ = db.call_proc(
        "Add_To_Cart", (cart_id, body.product_id, body.quantity, body.notes)
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The product was added to your cart.",
            failure_messages={
                -1: "This product does not exist, or the quantity is not valid.",
                -4: "This product is not available right now, or your cart is not active.",
                -5: "This business does not deliver to your active address. "
                    "Change your active address or choose another business.",
                -6: "You can order at most 10 of one product. Lower the quantity.",
            },
        )
    return ok(
        {"cart_id": cart_id, "items": _cart_items(cart_id)},
        "The product was added to your cart.",
    )


@router.post("/customer/cart/items/{product_id}/remove")
def remove_from_cart(product_id: int, user=customer_only):
    cart_id = _active_cart_id(user["user_id"])
    if cart_id is None:
        return fail(-9, "You do not have an active cart.")
    rc, _ = db.call_proc("Remove_From_Cart", (cart_id, product_id))
    if rc != 0:
        return proc_reply(
            rc,
            "The product was removed from your cart.",
            failure_messages={
                -1: "This product is not in your cart.",
                -4: "Your cart is not active.",
            },
        )
    return ok(
        {"cart_id": cart_id, "items": _cart_items(cart_id)},
        "The product was removed from your cart.",
    )


@router.get("/customer/vouchers")
def my_vouchers(user=customer_only):
    return ok(
        db.call_table_func("h_MyVouchers", (user["user_id"],)),
        "Your vouchers loaded.",
    )


# ---------------------------------------------------------------- checkout

@router.post("/customer/checkout/preview")
def checkout_preview(body: Optional[CheckoutPreviewBody] = None, user=customer_only):
    voucher_id = body.voucher_id if body else None
    customer_id = user["user_id"]
    cart_id = _active_cart_id(customer_id)
    if cart_id is None:
        return fail(-9, "Your cart is empty. Add products before checking out.")
    items = _cart_items(cart_id)
    if not items:
        return fail(-9, "Your cart is empty. Add products before checking out.")

    subtotal = sum(float(i["line_total"]) for i in items)

    profile = db.call_table_func("h_CustomerProfile", (customer_id,))
    zone_id = profile[0].get("active_zone_id") if profile else None
    fee = 0.0
    if zone_id is not None:
        zones = db.query_view("h_ZoneList", "zone_id = ?", (zone_id,))
        if zones:
            fee = float(zones[0]["delivery_fee"])

    discount = 0.0
    if voucher_id is not None:
        mine = db.call_table_func("h_MyVouchers", (customer_id,))
        if not any(v["voucher_id"] == voucher_id for v in mine):
            return fail(-1, "This voucher is not valid for you.")
        # Calculate_Voucher_Discount needs the subtotal as well as the voucher.
        discount = float(
            db.call_scalar(
                "Calculate_Voucher_Discount",
                (voucher_id, Decimal(str(round(subtotal, 2)))),
            )
            or 0
        )
        if discount < 0:
            return fail(-1, "This voucher could not be applied.")

    businesses = {}
    for item in items:
        entry = businesses.setdefault(
            item["business_id"],
            {
                "business_id": item["business_id"],
                "business_name": item["business_name"],
                "subtotal": 0.0,
                "delivery_fee": fee,
                "items": [],
            },
        )
        entry["subtotal"] = round(entry["subtotal"] + float(item["line_total"]), 2)
        entry["items"].append(item)
    business_list = []
    for entry in businesses.values():
        entry["total"] = round(entry["subtotal"] + entry["delivery_fee"], 2)
        business_list.append(entry)

    fees = round(len(businesses) * fee, 2)
    total = round(subtotal + fees - discount, 2)
    return ok(
        {
            "cart_id": cart_id,
            "subtotal": round(subtotal, 2),
            "delivery_fees": fees,
            "discount": round(discount, 2),
            "total": total,
            "businesses": business_list,
        },
        "Here is what you will pay.",
    )


@router.post("/customer/checkout")
def checkout(body: CheckoutBody, user=customer_only):
    customer_id = user["user_id"]
    cart_id = _active_cart_id(customer_id)
    if cart_id is None:
        return fail(-9, "Your cart is empty. Add products before checking out.")
    rc, _ = db.call_proc(
        "Checkout_Cart",
        (
            cart_id,
            body.voucher_id,
            body.payment_method,
            body.card_id if body.payment_method == "Card" else None,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "Your order is placed.",
            failure_messages={
                -1: "Some of the checkout details are not valid. Please check them and try again.",
                -3: "Your account is blacklisted, so you cannot check out. Contact support.",
                -4: "Your cart cannot be checked out in its current state. "
                    "A product may be unavailable, or a business may be closed.",
                -5: "A business in your cart does not deliver to your active address. "
                    "Change your active address or remove those products.",
                -7: "Your wallet balance is not enough, or the card is not valid. "
                    "Choose Cash or Card.",
                -8: "No rider is available in your zone right now. Try again in a few minutes.",
                -9: "Your cart is empty. Add products before checking out.",
            },
        )
    # Checkout_Cart returns no order ID, so the new order is the newest one
    # in this customer's order history.
    orders = _my_orders(customer_id)
    new_order = None
    if orders:
        new_order = max(orders, key=lambda o: (o["order_date"], o["order_id"]))
    return ok(new_order, "Your order is placed.")


# ---------------------------------------------------------------- browsing

@router.get("/customer/businesses/search")
def search_businesses(keyword: str = Query(..., min_length=1), user=customer_only):
    rows = db.call_table_func("Search_Platform", (user["user_id"], keyword))
    return ok(rows, "Search results loaded.")


@router.get("/customer/businesses/category")
def businesses_by_category(
    category: str = Query(..., min_length=1),
    address_id: int = Query(...),
    user=customer_only,
):
    if not _owns_address(user["user_id"], address_id):
        return fail(-3, "This address is not yours.")
    rows = db.call_table_func(
        "Nearby_Businesses_By_Category", (address_id, category)
    )
    return ok(rows, "Businesses loaded.")


@router.get("/customer/businesses/{business_id}")
def business_details(business_id: int, user=customer_only):
    details = db.call_table_func("h_BusinessDetails", (business_id,))
    if not details:
        return fail(-1, "This business does not exist.")
    products = db.call_table_func("h_BusinessProducts", (business_id,))
    ratings = db.query_view(
        "BusinessRatingsSummary", "business_id = ?", (business_id,)
    )
    return ok(
        {
            "details": details[0],
            "products": products,
            "rating": ratings[0] if ratings else None,
        },
        "Business loaded.",
    )


# ---------------------------------------------------------------- favorites

@router.post("/customer/favorites/toggle")
def toggle_favorite(body: FavoriteBody, user=customer_only):
    rc, _ = db.call_proc(
        "Toggle_Favorite", (user["user_id"], body.item_id, body.item_type)
    )
    if rc != 0:
        return proc_reply(
            rc,
            "Your favorites were updated.",
            failure_messages={
                -1: "This business or product does not exist.",
                -3: "You are not allowed to do this.",
            },
        )
    # The procedure toggles without saying which way. For products the new
    # state can be read back; there is no helper listing favorite businesses.
    favorited = None
    if body.item_type == "Product":
        favs = db.call_table_func("My_Favorites", (user["user_id"],))
        favorited = any(f["product_id"] == body.item_id for f in favs)
    message = "Your favorites were updated."
    if favorited is True:
        message = "Added to your favorites."
    elif favorited is False:
        message = "Removed from your favorites."
    return ok(
        {
            "item_id": body.item_id,
            "item_type": body.item_type,
            "favorited": favorited,
        },
        message,
    )


@router.get("/customer/favorites")
def my_favorites(user=customer_only):
    return ok(
        db.call_table_func("My_Favorites", (user["user_id"],)),
        "Your favorite products loaded.",
    )


@router.get("/customer/recommended")
def recommended(user=customer_only):
    return ok(
        db.call_table_func("Recommended_Products", (user["user_id"],)),
        "Recommended products loaded.",
    )


# ---------------------------------------------------------------- orders

@router.get("/customer/orders")
def my_orders(user=customer_only):
    orders = _my_orders(user["user_id"])
    zone_perf = db.query_view("ZoneDeliveryPerformance")
    avg_by_zone = {r["zone_name"]: r["avg_tracking_time"] for r in zone_perf}
    for order in orders:
        subs = db.call_table_func("h_OrderSubOrders", (order["order_id"],))
        avg = avg_by_zone.get(order["zone_name"])
        order_dt = None
        if order.get("order_date"):
            order_dt = datetime.fromisoformat(order["order_date"])
        etas = []
        for sub in subs:
            if sub["status"] in ("Placed", "Assigned", "Picked Up") and order_dt is not None:
                # Estimated arrival: business expected delivery time plus the
                # zone's real average delivery time (contract open decision 2).
                minutes = float(sub.get("expected_delivery_time") or 0) + float(avg or 0)
                eta = order_dt + timedelta(minutes=minutes)
                sub["estimated_arrival"] = eta.isoformat()
                etas.append(eta)
            else:
                sub["estimated_arrival"] = None
        order["suborders"] = subs
        order["estimated_arrival"] = max(etas).isoformat() if etas else None
    return ok(orders, "Your orders loaded.")


@router.post("/customer/orders/{order_id}/cancel")
def cancel_order(order_id: int, user=customer_only):
    order = _owns_order(user["user_id"], order_id)
    if order is None:
        return fail(-1, "This order does not exist.")
    # Cancel_Order returns no refund amount; the refund is the full remaining
    # amount (total minus what was already refunded).
    refund = float(order["total_amount"]) - float(order["refunded_amount"] or 0)
    rc, _ = db.call_proc("Cancel_Order", (order_id,))
    if rc != 0:
        return proc_reply(
            rc,
            "Your order was cancelled.",
            failure_messages={
                -1: "This order does not exist.",
                -4: "This order cannot be cancelled because a part of it was already picked up.",
            },
        )
    return ok(
        {"order_id": order_id, "refund_amount": round(refund, 2)},
        f"Your order was cancelled. {refund:.2f} EGP will be refunded.",
    )


@router.post("/customer/orders/{order_id}/reorder")
def reorder_order(order_id: int, body: ReorderBody, user=customer_only):
    if _owns_order(user["user_id"], order_id) is None:
        return fail(-1, "This order does not exist.")
    if not _owns_address(user["user_id"], body.address_id):
        return fail(-3, "This address is not yours.")
    rc, _ = db.call_proc("Reorder", (order_id, body.address_id))
    if rc != 0:
        return proc_reply(
            rc,
            "Your past order was added to a new cart.",
            failure_messages={
                -1: "This order does not exist.",
                -2: "You already have an active cart for this address.",
                -3: "You are not allowed to reorder this order.",
                -5: "This order does not deliver to that address. Choose another address.",
                -9: "Nothing from this order can be ordered again. "
                    "The products may be unavailable now.",
            },
        )
    # Reorder creates a new cart, not an order; return that cart.
    cart_id, items = _cart_data(user["user_id"])
    return ok(
        {"cart_id": cart_id, "items": items},
        "Your past order was added to a new cart.",
    )


@router.post("/customer/orders/suborders/{suborder_id}/feedback")
def submit_feedback(suborder_id: int, body: FeedbackBody, user=customer_only):
    if not _owns_suborder(user["user_id"], suborder_id):
        return fail(-3, "This order is not yours.")
    rc, _ = db.call_proc(
        "Submit_Feedback",
        (suborder_id, body.headline, body.description, body.rating),
    )
    return proc_reply(
        rc,
        "Thank you for your feedback.",
        failure_messages={
            -1: "Some of the feedback details are not valid. The rating must be between 1 and 5.",
            -2: "You already left feedback for this part of the order.",
            -4: "You can only leave feedback after the order is delivered.",
        },
    )


@router.post("/customer/orders/suborders/{suborder_id}/rate-rider")
def rate_rider(suborder_id: int, body: RateRiderBody, user=customer_only):
    if not _owns_suborder(user["user_id"], suborder_id):
        return fail(-3, "This order is not yours.")
    rc, _ = db.call_proc("Rate_Rider", (suborder_id, body.rider_rating))
    return proc_reply(
        rc,
        "Thank you for rating the rider.",
        failure_messages={
            -1: "The rating must be between 1 and 5.",
            -2: "You already rated the rider for this delivery.",
            -4: "You can only rate the rider after the order is delivered.",
        },
    )
