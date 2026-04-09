from fastapi import Request
from fastapi.responses import RedirectResponse

from app.core.config import settings


def is_authenticated(request: Request) -> bool:
    return request.session.get("admin_user") is not None


def require_admin(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def check_credentials(username: str, password: str) -> bool:
    return (
        username == settings.ADMIN_USERNAME
        and password == settings.ADMIN_PASSWORD
    )