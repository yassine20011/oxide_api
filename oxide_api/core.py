import asyncio
import inspect
import json
from typing import Any, Callable, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
import oxide_api._rustcore as _rustcore
from oxide_api.decorators import HANDLERS, SCHEMAS

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
    if getattr(app, "_rust_synced", False):
        return
    app._rust_synced = True
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        route_id = getattr(endpoint, "__rust_route_id__", None)
        if not route_id and hasattr(endpoint, "__wrapped__"):
            route_id = getattr(endpoint.__wrapped__, "__rust_route_id__", None)

        if route_id:
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
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", ["GET"])
            for m in methods:
                if path:
                    _rustcore.register_route(m, path, route_id, param_types, schema)

def prepare_handler_args(handler: Callable, params: dict) -> dict:
    sig = inspect.signature(handler)
    kwargs = {}
    body = params.pop("__body__", None)

    for param_name, param in sig.parameters.items():
        if param_name in params:
            kwargs[param_name] = params[param_name]
        elif body is not None:
            if isinstance(body, dict) and param_name in body:
                kwargs[param_name] = body[param_name]
            elif param.annotation in (dict, Dict, Any, inspect.Parameter.empty) or len(sig.parameters) == 1:
                kwargs[param_name] = body
            elif isinstance(body, dict) and param.name in ("user", "payload", "body", "data"):
                kwargs[param_name] = body

    return kwargs

async def send_json(send, status_code: int, content: Any):
    if isinstance(content, (bytes, bytearray)):
        payload = content
    elif isinstance(content, str):
        payload = content.encode("utf-8")
    else:
        payload = json.dumps(content).encode("utf-8")

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            (b"content-type", b"application/json"),
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

    _sync_app_routes(self)

    path = scope.get("path", "")
    method = scope.get("method", "GET").upper()

    if path in ("/openapi.json", "/docs", "/redoc") or path.startswith(("/docs/", "/redoc/")):
        await _original_fastapi_call(self, scope, receive, send)
        return

    matched = _rustcore.match_route(method, path)
    if matched is None:
        has_fastapi_route = any(
            getattr(r, "path", None) == path and method in getattr(r, "methods", set())
            for r in self.routes
        )
        if has_fastapi_route:
            await _original_fastapi_call(self, scope, receive, send)
            return
        await send_json(send, 404, {"detail": "Not Found"})
        return

    body_bytes = b""
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        more_body = True
        while more_body:
            msg = await receive()
            body_bytes += msg.get("body", b"")
            more_body = msg.get("more_body", False)

    query_str = scope.get("query_string", b"").decode("latin-1")
    res = _rustcore.handle_request(method, path, query_str, body_bytes)
    if res is None:
        await send_json(send, 404, {"detail": "Not Found"})
        return

    status_code, route_id, data = res

    if status_code == 422:
        await send_json(send, 422, data)
        return

    handler = HANDLERS.get(route_id)
    if handler is None:
        await send_json(send, 500, {"detail": f"Handler '{route_id}' not found"})
        return

    args = prepare_handler_args(handler, dict(data))
    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(**args)
        else:
            result = handler(**args)
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