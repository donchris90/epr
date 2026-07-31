"""
Cursor-based pagination helper (SRS Section 6.1) — offset pagination
degrades on large transactional tables, so every list endpoint should
use this instead.
"""
import base64
from flask import request


def encode_cursor(value) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode()


def decode_cursor(cursor: str):
    if not cursor:
        return None
    return base64.urlsafe_b64decode(cursor.encode()).decode()


def get_pagination_params(default_limit: int = 50, max_limit: int = 200):
    cursor = decode_cursor(request.args.get("cursor"))
    limit = min(int(request.args.get("limit", default_limit)), max_limit)
    return cursor, limit


def envelope(items, next_cursor=None):
    body = {"data": items}
    if next_cursor:
        body["next_cursor"] = encode_cursor(next_cursor)
    return body
