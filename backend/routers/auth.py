"""Auth endpoints: register, login, logout, me.

Login flow (per the API contract): call the validation function with the
username and password. If it returns 1, call h_GetUserId for the ID and create
the session. If it returns 0, the message is "Wrong username or password".
Admins only log in; there is no admin self-register.
"""

from fastapi import APIRouter, Request

import auth
import db
from messages import fail, ok, proc_reply
from models import LoginBody, RegisterBase, RiderRegister

router = APIRouter(tags=["auth"])


def _register(proc_name, body: RegisterBase):
    rc, _ = db.call_proc(
        proc_name,
        (
            body.first_name,
            body.middle_name,
            body.last_name,
            body.username,
            body.password,
            body.email,
            body.phone,
            body.dob,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "Your account was created.",
            failure_messages={
                -1: "Some of the information is not valid. Please check it and try again.",
                -2: "This username or email is already taken. Please choose another one.",
            },
        )
    user_id = db.call_scalar("h_GetUserId", (body.username,))
    return ok(
        {"user_id": user_id, "username": body.username},
        "Your account was created. You can now log in.",
    )


@router.post("/auth/customer/register")
def register_customer(body: RegisterBase):
    return _register("Customer_Register", body)


@router.post("/auth/partner/register")
def register_partner(body: RegisterBase):
    return _register("Partner_Register", body)


@router.post("/auth/rider/register")
def register_rider(body: RiderRegister):
    rc, _ = db.call_proc(
        "Rider_Register",
        (
            body.first_name,
            body.middle_name,
            body.last_name,
            body.username,
            body.password,
            body.email,
            body.phone,
            body.dob,
            body.vehicle_type,
            body.plate_no,
            body.license_no,
            body.zone_id,
        ),
    )
    if rc != 0:
        return proc_reply(
            rc,
            "Your account was created.",
            failure_messages={
                -1: "Some of the information is not valid. Please check it and try again.",
                -2: "This plate number or licence number is already registered. "
                    "Please check it and try again.",
            },
        )
    user_id = db.call_scalar("h_GetUserId", (body.username,))
    return ok(
        {"user_id": user_id, "username": body.username},
        "Your account was created. You can now log in.",
    )


def _login(request: Request, user_type: str, body: LoginBody):
    user_id = auth.check_login(user_type, body.username, body.password)
    if user_id is None:
        return fail(-1, "Wrong username or password.")
    auth.start_session(request, user_type, user_id, body.username)
    profile, name = auth.profile_for(user_type, user_id)
    return ok(
        {
            "user_id": user_id,
            "user_type": user_type,
            "username": body.username,
            "name": name,
            "profile": profile,
        },
        "Welcome back.",
    )


@router.post("/auth/customer/login")
def login_customer(request: Request, body: LoginBody):
    return _login(request, "customer", body)


@router.post("/auth/partner/login")
def login_partner(request: Request, body: LoginBody):
    return _login(request, "partner", body)


@router.post("/auth/rider/login")
def login_rider(request: Request, body: LoginBody):
    return _login(request, "rider", body)


@router.post("/auth/admin/login")
def login_admin(request: Request, body: LoginBody):
    return _login(request, "admin", body)


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return ok(None, "You are signed out.")


@router.get("/auth/me")
def me(request: Request):
    user = auth.get_current_user(request)
    profile, name = auth.profile_for(user["user_type"], user["user_id"])
    return ok(
        {
            "user_id": user["user_id"],
            "user_type": user["user_type"],
            "username": user.get("username"),
            "name": name,
            "profile": profile,
        },
        "Signed in.",
    )
