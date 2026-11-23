import secrets
from typing import Any

from flask import Flask, abort, current_app, jsonify, render_template, request, session


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return str(session["csrf_token"])


def error_response(code: int, message: str) -> Any:
    if request.is_json:
        return jsonify(error=message), code
    return render_template("error.html", code=code, message=message), code


def init_security(app: Flask) -> None:
    app.context_processor(lambda: {"csrf_token": csrf_token})

    @app.before_request
    def validate_csrf() -> Any:
        if not current_app.config.get("CSRF_ENABLED", True):
            return None
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        payload = request.get_json(silent=True) or {}
        token = (
            request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token")
            or (payload.get("csrf_token") if isinstance(payload, dict) else None)
        )
        expected = session.get("csrf_token", "")
        if not token or not secrets.compare_digest(str(token), str(expected)):
            abort(400, description="Invalid CSRF token.")
        return None

    @app.errorhandler(400)
    def handle_400(error: Any) -> Any:
        return error_response(400, getattr(error, "description", None) or "Bad request.")

    @app.errorhandler(404)
    def handle_404(error: Any) -> Any:
        return error_response(404, "Page not found.")

    @app.errorhandler(500)
    def handle_500(error: Any) -> Any:
        return error_response(500, "Something went wrong.")
