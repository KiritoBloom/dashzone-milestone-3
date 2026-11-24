"""Rider endpoints (Adam).

The rider is the signed-in rider. No rider ID in the request; it comes from
the session. Marking a delivery Picked Up or Delivered is only allowed for a
delivery assigned to this rider.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

import auth
import db
from messages import fail, ok, proc_reply
from models import AvailabilityBody
from routers.common import date_range

router = APIRouter(tags=["rider"])
rider_only = Depends(auth.require_type("rider"))


@router.get("/rider/me")
def rider_me(user=rider_only):
    rows = db.call_table_func("h_RiderProfile", (user["user_id"],))
    if not rows:
        return fail(-1, "Rider profile not found.")
    return ok(rows[0], "Rider profile loaded.")


@router.post("/rider/availability")
def set_availability(body: AvailabilityBody, user=rider_only):
    rc, _ = db.call_proc(
        "Set_Rider_Availability", (user["user_id"], body.is_available)
    )
    return proc_reply(
        rc,
        "You are available now." if body.is_available else "You are unavailable now.",
        failure_messages={-3: "This rider does not exist."},
    )


@router.get("/rider/deliveries")
def active_deliveries(user=rider_only):
    rows = db.call_table_func("My_Active_Deliveries", (user["user_id"],))
    return ok(rows, "Your active deliveries loaded.")


def _my_delivery_id(user_id: int, delivery_id: int) -> bool:
    rows = db.call_table_func("My_Active_Deliveries", (user_id,))
    return any(d["delivery_id"] == delivery_id for d in rows)


@router.post("/rider/deliveries/{delivery_id}/pickup")
def mark_picked_up(delivery_id: int, user=rider_only):
    if not _my_delivery_id(user["user_id"], delivery_id):
        return fail(-3, "This delivery is not assigned to you.")
    rc, _ = db.call_proc("Mark_Picked_Up", (delivery_id,))
    return proc_reply(
        rc,
        "The delivery was marked as Picked Up.",
        failure_messages={
            -1: "This delivery does not exist.",
            -4: "This delivery cannot be picked up in its current state.",
        },
    )


@router.post("/rider/deliveries/{delivery_id}/deliver")
def mark_delivered(delivery_id: int, user=rider_only):
    if not _my_delivery_id(user["user_id"], delivery_id):
        return fail(-3, "This delivery is not assigned to you.")
    rc, _ = db.call_proc("Mark_Delivered", (delivery_id,))
    return proc_reply(
        rc,
        "The delivery was marked as Delivered.",
        failure_messages={
            -1: "This delivery does not exist.",
            -4: "This delivery must be Picked Up before it can be marked as Delivered.",
        },
    )


@router.get("/rider/earnings")
def earnings(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user=rider_only,
):
    start, end = date_range(from_date, to_date)
    rows = db.call_table_func("My_Earnings", (user["user_id"], start, end))
    return ok(rows[0] if rows else None, "Your earnings loaded.")


@router.get("/rider/rating")
def rating(user=rider_only):
    rows = db.call_table_func("My_Rating_Summary", (user["user_id"],))
    return ok(rows[0] if rows else None, "Your rating loaded.")


@router.get("/rider/history")
def history(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user=rider_only,
):
    start, end = date_range(from_date, to_date)
    rows = db.call_table_func("My_Delivery_History", (user["user_id"], start, end))
    return ok(rows, "Your delivery history loaded.")
