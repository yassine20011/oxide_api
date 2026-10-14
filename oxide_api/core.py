import asyncio
import inspect
import json
from typing import Any, Callable, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
import oxide_api._rustcore as _rustcore
from oxide_api.decorators import HANDLERS, SCHEMAS

try:
    import orjson
    def dump_json_bytes(content: Any) -> bytes:
        return orjson.dumps(content)
except ImportError:
    def dump_json_bytes(content: Any) -> bytes:
        return json.dumps(content).encode("utf-8")

STATIC_HEADER_CONTENT_TYPE = (b"content-type", b"application/json")
NOT_FOUND_BODY = b'{"detail":"Not Found"}'
NOT_FOUND_HEADERS = [
    STATIC_HEADER_CONTENT_TYPE,
    (b"content-length", b"22"),
]

class HandlerMetadata:
    __slots__ = ("handler", "is_async", "single_body_param", "accepts_kwargs")

    def __init__(self, handler: Callable):
        self.handler = handler
        self.is_async = inspect.iscoroutinefunction(handler)
        sig = inspect.signature(handler)
        self.accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        self.single_body_param = None
        params = list(sig.parameters.values())
        if len(params) == 1:
            p = params[0]
            if p.name in ("user", "payload", "body", "data") or p.annotation in (dict, Dict, Any):
                self.single_body_param = p.name

HANDLER_CACHE: Dict[str, HandlerMetadata] = {}

def get_handler_metadata(route_id: str, raw_func: Callable) -> HandlerMetadata:
    cached = HANDLER_CACHE.get(route_id)
    if cached is None:
        cached = HandlerMetadata(raw_func)
        HANDLER_CACHE[route_id] = cached
    return cached

def match_route(method: str, path: str):
    return _rustcore.match_route(method, path)

def validate_input(data: Any, schema: Optional[Dict[str, str]] = None):
    return _rustcore.validate_input(data, schema)

def validate_request_body(body: Any, schema: Optional[Dict[str, str]] = None):
    result = validate_input(body, schema)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("errors"))
    return result.get("data")

def register_route(
    method: str,
    path: str,
    route_id: str,
    param_types: Optional[Dict[str, str]] = None,
    body_schema: Optional[Dict[str, str]] = None,
):
    _rustcore.register_route(method, path, route_id, param_types, body_schema)

def _sync_app_routes(app: FastAPI):
    if getattr(app, "_routes_synced", False):
        return
    app._routes_synced = True

    has_oxide = False
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        route_id = getattr(endpoint, "__rust_route_id__", None)
        if not route_id and hasattr(endpoint, "__wrapped__"):
            route_id = getattr(endpoint.__wrapped__, "__rust_route_id__", None)

        if route_id:
            has_oxide = True
            param_types = getattr(
                endpoint,
                "__rust_param_types__",
                getattr(getattr(endpoint, "__wrapped__", None), "__rust_param_types__", {}),
            )
            schema = getattr(
                endpoint,
                "__rust_body_schema__",
                getattr(getattr(endpoint, "__wrapped__", None), "__rust_body_schema__", None),
            )
            raw_func = getattr(
                endpoint,
                "__rust_func__",
                getattr(getattr(endpoint, "__wrapped__", None), "__rust_func__", endpoint),
            )
            HANDLERS[route_id] = raw_func
            get_handler_metadata(route_id, raw_func)

            path = getattr(route, "path", None)
            methods = getattr(route, "methods", ["GET"])
            for m in methods:
                if path:
                    _rustcore.register_route(m, path, route_id, param_types, schema)
        else:
            path = getattr(route, "path", None)
            if path and not (path in ("/openapi.json", "/docs", "/redoc") or path.startswith(("/docs/", "/redoc/"))):
                methods = getattr(route, "methods", ["GET"])
                for m in methods:
                    try:
                        _rustcore.register_route(m, path, "__fastapi__", {}, None)
                    except Exception:
                        pass

    app._has_oxide_routes = has_oxide
    app._fastapi_routes = {
        (m, getattr(r, "path", None))
        for r in app.routes
        for m in getattr(r, "methods", ["GET"])
    }

def prepare_args_fast(meta: HandlerMetadata, params: dict) -> dict:
    body = params.pop("__body__", None)
    if body is not None:
        if meta.single_body_param:
            params[meta.single_body_param] = body
        elif isinstance(body, dict):
            params.update(body)
    return params

async def send_json(send, status_code: int, content: Any):
    if isinstance(content, (bytes, bytearray)):
        payload = content
    elif isinstance(content, str):
        payload = content.encode("utf-8")
    else:
        payload = dump_json_bytes(content)

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            STATIC_HEADER_CONTENT_TYPE,
            (b"content-length", str(len(payload)).encode("latin-1")),
        ],
    })
    await send({
        "type": "http.response.body",
        "body": payload,
    })

_original_fastapi_call = FastAPI.__call__

async def _oxide_fastapi_call(self, scope, receive, send):
    if scope.get("type") != "http":
        await _original_fastapi_call(self, scope, receive, send)
        return

    if not getattr(self, "_routes_synced", False):
        _sync_app_routes(self)

    if not getattr(self, "_has_oxide_routes", True):
        await _original_fastapi_call(self, scope, receive, send)
        return

    path = scope.get("path", "")
    method = scope.get("method", "GET").upper()

    if path in ("/openapi.json", "/docs", "/redoc") or path.startswith(("/docs/", "/redoc/")):
        await _original_fastapi_call(self, scope, receive, send)
        return

    body_bytes = None
    if method in ("POST", "PUT", "PATCH"):
        body_buf = []
        more_body = True
        while more_body:
            msg = await receive()
            b = msg.get("body", b"")
            if b:
                body_buf.append(b)
            more_body = msg.get("more_body", False)
        body_bytes = b"".join(body_buf) if body_buf else b""

    query_str = scope.get("query_string", b"").decode("latin-1")
    res = _rustcore.handle_request(method, path, query_str, body_bytes)
    if res is None:
        if (method, path) in getattr(self, "_fastapi_routes", ()):
            await _original_fastapi_call(self, scope, receive, send)
            return
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": NOT_FOUND_HEADERS,
        })
        await send({
            "type": "http.response.body",
            "body": NOT_FOUND_BODY,
        })
        return

    status_code, route_id, data = res

    if route_id == "__fastapi__":
        await _original_fastapi_call(self, scope, receive, send)
        return

    if status_code == 422:
        await send_json(send, 422, data)
        return

    raw_func = HANDLERS.get(route_id)
    if raw_func is None:
        await send_json(send, 500, {"detail": f"Handler '{route_id}' not found"})
        return

    meta = get_handler_metadata(route_id, raw_func)
    args = prepare_args_fast(meta, dict(data))

    try:
        if meta.is_async:
            result = await raw_func(**args)
        else:
            result = raw_func(**args)
    except HTTPException as exc:
        await send_json(send, exc.status_code, {"detail": exc.detail})
        return

    if isinstance(result, Response):
        await result(scope, receive, send)
    else:
        await send_json(send, 200, result)

FastAPI.__call__ = _oxide_fastapi_call

app = FastAPI()

@app.middleware("http")
async def rust_middleware(request, call_next):
    route_info = match_route(request.method, request.url.path)
    if route_info is None:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    route_id, params = route_info
    request.state.route_id = route_id
    request.state.params = params
    return await call_next(request)