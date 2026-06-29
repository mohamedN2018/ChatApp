"""Request metadata helpers (client IP, user agent, device label)."""

from __future__ import annotations


def client_ip(request) -> str | None:
    """Best-effort client IP.

    Behind the Nginx reverse proxy, ``X-Forwarded-For`` is set; the left-most
    entry is the originating client. Falls back to ``REMOTE_ADDR``.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:512]


def device_label(request) -> str:
    """A short, human-friendly device descriptor derived from the user agent."""
    ua = user_agent(request)
    if not ua:
        return "Unknown device"
    lowered = ua.lower()
    os_name = next(
        (
            name
            for token, name in (
                ("windows", "Windows"),
                ("mac os", "macOS"),
                ("iphone", "iPhone"),
                ("ipad", "iPad"),
                ("android", "Android"),
                ("linux", "Linux"),
            )
            if token in lowered
        ),
        "Unknown OS",
    )
    browser = next(
        (
            name
            for token, name in (
                ("edg", "Edge"),
                ("chrome", "Chrome"),
                ("firefox", "Firefox"),
                ("safari", "Safari"),
            )
            if token in lowered
        ),
        "browser",
    )
    return f"{browser} on {os_name}"
