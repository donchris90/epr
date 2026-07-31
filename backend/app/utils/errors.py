"""
RFC 7807 Problem Details error format (SRS Section 6.1):
{type, title, status, detail, instance}
"""
from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, title: str, status: int = 400, detail: str = None, type_: str = "about:blank"):
        super().__init__(title)
        self.title = title
        self.status = status
        self.detail = detail
        self.type = type_


def _problem(type_, title, status, detail=None):
    body = {"type": type_, "title": title, "status": status, "instance": request.path}
    if detail:
        body["detail"] = detail
    return jsonify(body), status


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return _problem(err.type, err.title, err.status, err.detail)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return _problem("about:blank", err.name, err.code, err.description)

    @app.errorhandler(Exception)
    def handle_uncaught(err: Exception):
        app.logger.exception("Unhandled exception")
        return _problem("about:blank", "Internal Server Error", 500)
