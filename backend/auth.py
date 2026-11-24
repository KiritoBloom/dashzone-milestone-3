"""Sessions and role checks.

On login the backend creates a signed-cookie session holding user_id and
user_type (see main.py, SessionMiddleware). The frontend never sends a user
ID; every endpoint reads it from the session here.

- get_current_user: returns the signed-in user or raises AuthError (401).
- require_type: FastAPI dependency factory, enforces the user type per router.
- is_super_admin: checks h_IsSuperAdmin; Super Admin-only actions use it and
  return code -3 with a clear message when a Zone Admin tries them.
"""

import db
from fastapi import Request

LOGIN_FUNCTIONS = {
    "customer": "CustomerLoginValidation",
    "partner": "PartnerLoginValidation",
    "rider": "RiderLoginValidation",
    "admin": "AdminLoginValidation",
}


class AuthError(Exception):
    def __init__(self, status_code=401, message="You are not signed in. Please log in."):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def get_current_user(request: Request):
    user = request.session.get("user")
    if not user or "user_id" not in user or "user_type" not in user:
        raise AuthError(401, "You are not signed in. Please log in.")
    return user


def require_type(*types):
    def _dependency(request: Request):
        user = get_current_user(request)
        if user["user_type"] not in types:
            raise AuthError(
                403,
                "You do not have access to this. Please sign in with the right account type.",
            )
        return user

    return _dependency


def is_super_admin(admin_id: int) -> bool:
    return bool(db.call_scalar("h_IsSuperAdmin", (admin_id,)))


def check_login(user_type: str, username: str, password: str):
    """Validate a login. Returns the user_id, or None when the credentials
    are wrong (the validation function returns 0)."""
    valid = db.call_scalar(LOGIN_FUNCTIONS[user_type], (username, password))
    if not valid:
        return None
    user_id = db.call_scalar("h_GetUserId", (username,))
    if user_id is None:
        return None
    return int(user_id)


def start_session(request, user_type: str, user_id: int, username: str):
    request.session["user"] = {
        "user_id": user_id,
        "user_type": user_type,
        "username": username,
    }


def profile_for(user_type: str, user_id: int):
    """The profile row for the signed-in user, plus their display name.

    Note: the Milestone 2 SQL has no partner profile helper, so for a partner
    the business row is used (its name is the business name, or None when the
    partner has not registered a business yet).
    """
    if user_type == "customer":
        rows = db.call_table_func("h_CustomerProfile", (user_id,))
        if not rows:
            return None, None
        return rows[0], rows[0].get("customer_name")
    if user_type == "rider":
        rows = db.call_table_func("h_RiderProfile", (user_id,))
        if not rows:
            return None, None
        return rows[0], rows[0].get("rider_name")
    if user_type == "admin":
        rows = db.call_table_func("h_AdminProfile", (user_id,))
        if not rows:
            return None, None
        return rows[0], rows[0].get("admin_name")
    rows = db.call_table_func("h_MyBusiness", (user_id,))
    if not rows:
        return None, None
    return rows[0], rows[0].get("business_name")
