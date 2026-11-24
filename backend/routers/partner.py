"""Partner endpoints (Karim).

The business and products are the signed-in partner's own. No business ID
in the request; it comes from the session (looked up with h_MyBusiness).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

import auth
import db
from messages import fail, ok, proc_reply
from models import (
    ProductBody,
    PromotionBody,
    RegisterBusinessBody,
    ToggleProductBody,
    UpdateBusinessBody,
)
from routers.common import date_range

router = APIRouter(tags=["partner"])
partner_only = Depends(auth.require_type("partner"))


def _my_business(partner_id: int):
    rows = db.call_table_func("h_MyBusiness", (partner_id,))
    return rows[0] if rows else None


def _my_products(partner_id: int):
    return db.call_table_func("h_MyProducts", (partner_id,))


def _owns_product(partner_id: int, product_id: int) -> bool:
    return any(p["product_id"] == product_id for p in _my_products(partner_id))


@router.get("/partner/business")
def my_business(user=partner_only):
    business = _my_business(user["user_id"])
    if business is None:
        return ok(None, "You have not registered a business yet.")
    phones = db.call_table_func("h_BusinessPhones", (business["business_id"],))
    business["phones"] = [p["phone"] for p in phones]
    return ok(business, "Your business loaded.")


@router.post("/partner/business")
def register_business(body: RegisterBusinessBody, user=partner_only):
    rc, _ = db.call_proc(
        "Register_Business",
        (
            user["user_id"],
            body.name,
            body.description,
            body.link_website,
            body.zone_id,
            body.opening_hour,
            body.closing_hour,
            body.expected_delivery_time,
            body.phone,
            body.business_type,
            body.cuisine_type,
            body.food_category,
            body.pharmacy_type,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "Your business was registered and is waiting for approval.",
            failure_messages={
                -1: "Some of the business details are not valid. Please check them and try again.",
                -2: "You already have a business that is not Rejected. "
                    "You can only register again after a rejection.",
                -3: "You are not allowed to register a business.",
            },
        )
    return ok(_my_business(user["user_id"]), "Your business was registered and is waiting for approval.")


@router.post("/partner/business/update")
def update_business(body: UpdateBusinessBody, user=partner_only):
    business = _my_business(user["user_id"])
    if business is None:
        return fail(-1, "You have not registered a business yet.")
    rc, _ = db.call_proc(
        "Update_Business_Info",
        (
            business["business_id"],
            body.opening_hour,
            body.closing_hour,
            body.phone,
            body.link_website,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "Your business details were updated.",
            failure_messages={
                -1: "Some of the details are not valid. Please check them and try again.",
                -2: "This phone number is already saved for your business.",
            },
        )
    return ok(_my_business(user["user_id"]), "Your business details were updated.")


@router.get("/partner/products")
def my_products(user=partner_only):
    return ok(_my_products(user["user_id"]), "Your products loaded.")


@router.post("/partner/products")
def add_product(body: ProductBody, user=partner_only):
    business = _my_business(user["user_id"])
    if business is None:
        return fail(-1, "You have not registered a business yet.")
    rc, _ = db.call_proc(
        "Upsert_Product",
        (
            business["business_id"],
            None,
            body.name,
            body.description,
            body.category,
            body.price,
            body.is_available,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The product was added.",
            failure_messages={
                -1: "Some of the product details are not valid. Please check them and try again.",
                -4: "Your business is Suspended, so you cannot add products.",
            },
        )
    return ok(_my_products(user["user_id"]), "The product was added.")


@router.post("/partner/products/{product_id}")
def update_product(product_id: int, body: ProductBody, user=partner_only):
    business = _my_business(user["user_id"])
    if business is None:
        return fail(-1, "You have not registered a business yet.")
    if not _owns_product(user["user_id"], product_id):
        return fail(-3, "This product is not yours.")
    rc, _ = db.call_proc(
        "Upsert_Product",
        (
            business["business_id"],
            product_id,
            body.name,
            body.description,
            body.category,
            body.price,
            body.is_available,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The product was updated.",
            failure_messages={
                -1: "Some of the product details are not valid. "
                    "A discount cannot be more than half of the new price.",
                -4: "Your business is Suspended, so you cannot change products.",
            },
        )
    return ok(_my_products(user["user_id"]), "The product was updated.")


@router.post("/partner/products/{product_id}/toggle")
def toggle_product(product_id: int, body: ToggleProductBody, user=partner_only):
    if not _owns_product(user["user_id"], product_id):
        return fail(-3, "This product is not yours.")
    rc, _ = db.call_proc("Toggle_Product_Status", (product_id, body.is_available))
    if rc != 0:
        return proc_reply(
            rc,
            "The product is available now." if body.is_available else "The product was deactivated.",
            failure_messages={
                -1: "This product does not exist.",
                -4: "Your business is Suspended, so you cannot make products available.",
            },
        )
    return ok(_my_products(user["user_id"]), "The product is available now." if body.is_available else "The product was deactivated.")


@router.post("/partner/products/{product_id}/promotion")
def set_promotion(product_id: int, body: PromotionBody, user=partner_only):
    if not _owns_product(user["user_id"], product_id):
        return fail(-3, "This product is not yours.")
    rc, _ = db.call_proc(
        "Set_Product_Promotion", (product_id, body.discount_amount)
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The discount was removed." if body.discount_amount == 0 else "The discount was set.",
            failure_messages={
                -1: "The discount is not valid. It cannot be more than half of the product price.",
            },
        )
    return ok(
        _my_products(user["user_id"]),
        "The discount was removed." if body.discount_amount == 0 else "The discount was set.",
    )


@router.get("/partner/performance")
def performance(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user=partner_only,
):
    business = _my_business(user["user_id"])
    if business is None:
        return ok(
            {"sales": [], "feedback": None},
            "You have not registered a business yet.",
        )
    start, end = date_range(from_date, to_date)
    sales = db.call_table_func(
        "BusinessSalesReport", (business["business_id"], start, end)
    )
    feedback = db.call_table_func(
        "BusinessFeedbackOverview", (business["business_id"],)
    )
    return ok(
        {"sales": sales, "feedback": feedback[0] if feedback else None},
        "Your business performance loaded.",
    )
