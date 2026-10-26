from contextvars import ContextVar

_current_request = ContextVar("audit_current_request", default=None)


def get_current_request():
    return _current_request.get()


def get_current_user():
    """Authenticated user of the request in flight (resolved lazily so DRF/JWT auth is seen)."""
    request = _current_request.get()
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


def get_client_ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)
