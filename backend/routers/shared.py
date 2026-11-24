"""Shared endpoints: the zone list every registration and address form needs.
No sign-in required, because registration needs the zones before logging in.
"""

from fastapi import APIRouter

import db
from messages import ok

router = APIRouter(tags=["shared"])


@router.get("/zones")
def list_zones():
    zones = db.query_view("h_ZoneList")
    return ok(zones, "Zones loaded.")
