"""Response envelope and return-code messages.

Every endpoint returns the same shape:
    {"ok": bool, "code": int, "message": str, "data": ...}

`ok` is True exactly when `code` is 0. `code` is the Milestone 2 procedure's
return code (0 to -9). The message is always in the user's words and says how
to fix the problem; a raw SQL error or a bare error code is never returned.
"""

DEFAULT_MESSAGES = {
    0: "Done.",
    -1: "Some of the information is not valid. Please check it and try again.",
    -2: "This already exists. Please choose something else.",
    -3: "You are not allowed to do this.",
    -4: "This cannot be done in its current state.",
    -5: "This business does not deliver to your active address. "
        "Change your active address or choose another business.",
    -6: "You can order at most 10 of one product. Lower the quantity.",
    -7: "The payment could not be made. Check your balance or card, "
        "or choose another payment method.",
    -8: "No rider is available in your zone right now. Try again in a few minutes.",
    -9: "Your cart is empty. Add products before checking out.",
}


def reply(ok, code, message, data=None):
    return {"ok": ok, "code": code, "message": message, "data": data}


def ok(data=None, message="Done."):
    return reply(True, 0, message, data)


def fail(code, message=None, data=None):
    return reply(
        False,
        code,
        message or DEFAULT_MESSAGES.get(code, "Something went wrong. Please try again."),
        data,
    )


def proc_reply(code, success_message, data=None, failure_messages=None):
    """Build a reply from a stored procedure's return code.

    `failure_messages` maps specific codes to a message that fits this
    action; anything not overridden falls back to DEFAULT_MESSAGES.
    """
    if code == 0:
        return ok(data, success_message)
    messages = dict(DEFAULT_MESSAGES)
    if failure_messages:
        messages.update(failure_messages)
    return fail(
        code,
        messages.get(code, "Something went wrong. Please try again."),
        data,
    )
