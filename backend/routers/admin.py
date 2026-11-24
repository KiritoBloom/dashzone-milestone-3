"""Admin endpoints (Adham).

The signed-in admin's ID always comes from the session. The IDs in the URLs
are the record being acted on, not the signed-in user.

Super Admin only (checked here with h_IsSuperAdmin, returning code -3 for a
Zone Admin): create admin, assign or move a Zone Admin, suspend and reinstate
a business, create a zone, change a zone fee.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

import auth
import db
from messages import fail, ok, proc_reply
from models import (
    AssignZoneBody,
    BlacklistBody,
    CreateAdminBody,
    CreateZoneBody,
    IssueVoucherBody,
    SuspendBody,
    UpdateZoneFeeBody,
)
from routers.common import date_range

router = APIRouter(tags=["admin"])
admin_only = Depends(auth.require_type("admin"))


def _require_super_admin(admin_id: int):
    """Returns an error reply when the admin is not a Super Admin, else None."""
    if not auth.is_super_admin(admin_id):
        return fail(-3, "Only a Super Admin can do this.")
    return None


@router.get("/admin/me")
def admin_me(user=admin_only):
    rows = db.call_table_func("h_AdminProfile", (user["user_id"],))
    if not rows:
        return fail(-1, "Admin profile not found.")
    return ok(rows[0], "Admin profile loaded.")


@router.get("/admin/pending-businesses")
def pending_businesses(user=admin_only):
    return ok(db.query_view("PendingBusinessApprovals"), "Businesses awaiting approval.")


@router.post("/admin/businesses/{business_id}/approve")
def approve_business(business_id: int, user=admin_only):
    rc, _ = db.call_proc("Approve_Business", (business_id, user["user_id"]))
    return proc_reply(
        rc,
        "The business was approved.",
        failure_messages={
            -1: "This business does not exist.",
            -3: "You cannot manage a business outside your zone.",
            -4: "This business is not waiting for approval anymore.",
        },
    )


@router.post("/admin/businesses/{business_id}/reject")
def reject_business(business_id: int, user=admin_only):
    rc, _ = db.call_proc("Reject_Business", (business_id, user["user_id"]))
    return proc_reply(
        rc,
        "The business was rejected.",
        failure_messages={
            -1: "This business does not exist.",
            -3: "You cannot manage a business outside your zone.",
            -4: "This business is not waiting for approval anymore.",
        },
    )


@router.get("/admin/businesses")
def list_businesses(
    status: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None, alias="type"),
    user=admin_only,
):
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if business_type:
        where.append("business_type = ?")
        params.append(business_type)
    rows = db.query_view("allBusinessProfiles", " AND ".join(where), params)
    return ok(rows, "Businesses loaded.")


@router.post("/admin/businesses/{business_id}/suspend")
def suspend_business(business_id: int, body: SuspendBody, user=admin_only):
    err = _require_super_admin(user["user_id"])
    if err:
        return err
    rc, _ = db.call_proc(
        "Suspend_Business", (business_id, user["user_id"], body.reason)
    )
    return proc_reply(
        rc,
        "The business was suspended.",
        failure_messages={
            -1: "This business does not exist, or the reason is missing.",
            -3: "You cannot manage a business outside your zone.",
            -4: "Only an Active business can be suspended.",
        },
    )


@router.post("/admin/businesses/{business_id}/reinstate")
def reinstate_business(business_id: int, user=admin_only):
    err = _require_super_admin(user["user_id"])
    if err:
        return err
    rc, _ = db.call_proc("Reinstate_Business", (business_id, user["user_id"]))
    return proc_reply(
        rc,
        "The business was reinstated.",
        failure_messages={
            -1: "This business does not exist.",
            -4: "Only a Suspended business can be reinstated.",
        },
    )


@router.get("/admin/suspended-businesses")
def suspended_businesses(user=admin_only):
    return ok(db.query_view("h_SuspendedBusinesses"), "Suspended businesses loaded.")


@router.post("/admin/admins")
def create_admin(body: CreateAdminBody, user=admin_only):
    err = _require_super_admin(user["user_id"])
    if err:
        return err
    rc, _ = db.call_proc(
        "Create_Admin",
        (
            body.first_name,
            body.middle_name,
            body.last_name,
            body.username,
            body.password,
            body.email,
            body.phone,
            body.dob,
            body.role,
            body.zone_id,
            user["user_id"],
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "The admin account was created.",
            failure_messages={
                -1: "Some of the information is not valid. Please check it and try again.",
                -2: "This username or email is already taken. Please choose another one.",
                -3: "Only a Super Admin can create an admin.",
            },
        )
    admin_id = db.call_scalar("h_GetUserId", (body.username,))
    return ok(
        {"admin_id": admin_id, "username": body.username, "role": body.role},
        "The admin account was created.",
    )


@router.post("/admin/admins/{admin_id}/assign-zone")
def assign_zone(admin_id: int, body: AssignZoneBody, user=admin_only):
    err = _require_super_admin(user["user_id"])
    if err:
        return err
    rc, _ = db.call_proc(
        "Assign_Admin_Zone", (admin_id, body.zone_id, user["user_id"])
    )
    return proc_reply(
        rc,
        "The Zone Admin was assigned to the zone.",
        failure_messages={
            -1: "This admin is not a Zone Admin, or the zone does not exist.",
            -3: "Only a Super Admin can assign a zone.",
        },
    )


@router.get("/admin/admins")
def list_admins(user=admin_only):
    return ok(db.query_view("h_AdminList"), "Admins loaded.")


@router.post("/admin/vouchers")
def issue_voucher(body: IssueVoucherBody, user=admin_only):
    rc, _ = db.call_proc(
        "Issue_Voucher",
        (
            body.customer_id,
            body.promo_code,
            body.is_percentage,
            body.amount,
            body.expiry_date,
            user["user_id"],
        ),
    )
    return proc_reply(
        rc,
        f"The voucher {body.promo_code} was issued.",
        failure_messages={
            -1: "Some of the voucher details are not valid. Check the amount and the expiry date.",
            -2: "This promo code already exists. Choose another code.",
            -3: "You cannot issue a voucher to this customer.",
        },
    )


@router.get("/admin/vouchers")
def list_vouchers(user=admin_only):
    return ok(db.query_view("ActiveVouchers"), "Active vouchers loaded.")


@router.get("/admin/customers")
def list_customers(user=admin_only):
    return ok(db.query_view("h_CustomerList"), "Customers loaded.")


@router.post("/admin/customers/{customer_id}/blacklist")
def blacklist_customer(customer_id: int, body: BlacklistBody, user=admin_only):
    rc, _ = db.call_proc(
        "Blacklist_Customer", (customer_id, user["user_id"], body.reason)
    )
    return proc_reply(
        rc,
        "The customer was blacklisted.",
        failure_messages={
            -1: "This customer does not exist, or the reason is missing.",
            -3: "You cannot manage a customer outside your zone.",
            -4: "This customer is already blacklisted.",
        },
    )


@router.post("/admin/customers/{customer_id}/lift-blacklist")
def lift_blacklist(customer_id: int, user=admin_only):
    rc, _ = db.call_proc("Lift_Customer_Blacklist", (customer_id, user["user_id"]))
    return proc_reply(
        rc,
        "The blacklist was lifted.",
        failure_messages={
            -3: "Only the admin who set this blacklist can lift it.",
            -4: "This customer is not blacklisted.",
        },
    )


@router.get("/admin/blacklisted")
def list_blacklisted(user=admin_only):
    return ok(db.query_view("h_BlacklistedCustomers"), "Blacklisted customers loaded.")


@router.get("/admin/dashboard")
def dashboard(user=admin_only):
    health = db.call_table_func("Platform_Health_Snapshot", ())
    mismatched = db.call_table_func("Reconcile_Order_Totals", ())
    return ok(
        {
            "health": health[0] if health else None,
            "mismatched_orders": mismatched,
        },
        "Platform dashboard loaded.",
    )


@router.post("/admin/zones")
def create_zone(body: CreateZoneBody, user=admin_only):
    err = _require_super_admin(user["user_id"])
    if err:
        return err
    rc, _ = db.call_proc(
        "Create_Zone", (body.zone_name, body.delivery_fee, user["user_id"])
    )
    return proc_reply(
        rc,
        f"The zone {body.zone_name} was created.",
        failure_messages={
            -1: "The zone name or delivery fee is not valid.",
            -2: "A zone with this name already exists.",
            -3: "Only a Super Admin can create a zone.",
        },
    )


@router.post("/admin/zones/{zone_id}/fee")
def update_zone_fee(zone_id: int, body: UpdateZoneFeeBody, user=admin_only):
    err = _require_super_admin(user["user_id"])
    if err:
        return err
    rc, _ = db.call_proc(
        "Update_Zone_Fee", (zone_id, body.new_fee, user["user_id"])
    )
    return proc_reply(
        rc,
        "The zone delivery fee was updated.",
        failure_messages={
            -1: "This zone does not exist, or the fee is not valid.",
            -3: "Only a Super Admin can change a zone fee.",
        },
    )


@router.get("/admin/zones/compare")
def compare_zones(
    zone_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user=admin_only,
):
    start, end = date_range(from_date, to_date)
    report = []
    if zone_id is not None:
        report = db.call_table_func("ZoneOrderReport", (zone_id, start, end))
    return ok(
        {
            "businesses_per_zone": db.query_view("BusinessesPerZone"),
            "delivery_performance": db.query_view("ZoneDeliveryPerformance"),
            "zone_report": report[0] if report else None,
        },
        "Zone comparison loaded.",
    )


@router.get("/admin/revenue")
def daily_revenue(
    report_date: Optional[date] = Query(None, alias="date"),
    user=admin_only,
):
    rows = db.call_table_func(
        "Daily_Revenue_Report", (report_date or date.today(),)
    )
    return ok(rows, "Daily revenue loaded.")


@router.get("/admin/riders/top")
def top_riders(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user=admin_only,
):
    start, end = date_range(from_date, to_date)
    return ok(
        {
            "top_riders": db.call_table_func("TopRiders", (start, end)),
            "rider_performance": db.query_view("RiderPerformanceSummary"),
        },
        "Rider rankings loaded.",
    )


@router.get("/admin/market")
def market(user=admin_only):
    return ok(
        {
            "top_selling_products": db.query_view("TopSellingProducts"),
            "business_ratings": db.query_view("BusinessRatingsSummary"),
        },
        "Market overview loaded.",
    )
