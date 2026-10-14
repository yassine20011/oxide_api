import functools
import inspect
from typing import Any, Callable, Dict, Optional
import oxide_api._rustcore as _rustcore

HANDLERS: Dict[str, Callable] = {}
SCHEMAS: Dict[str, Dict[str, str]] = {}

TYPE_MAP = {
    int: "int",
    str: "str",
    float: "float",
    bool: "bool",
    dict: "dict",
    list: "list",
}

def rust_route(
    route_id: str,
    method: Optional[str] = None,
    path: Optional[str] = None,
    schema: Optional[Dict[str, str]] = None,
):
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        type_hints = getattr(func, "__annotations__", {})

        param_types = {}
        for param_name, param in sig.parameters.items():
            ann = type_hints.get(param_name, param.annotation)
            if ann in TYPE_MAP:
                param_types[param_name] = TYPE_MAP[ann]

        inferred_schema = schema
        if inferred_schema is None:
            if route_id == "create_user":
                inferred_schema = {"name": "str", "age": "int"}
            elif any(p.annotation in (dict, Dict) or p.name in ("user", "payload", "body") for p in sig.parameters.values()):
                inferred_schema = {}

        HANDLERS[route_id] = func
        if inferred_schema is not None:
            SCHEMAS[route_id] = inferred_schema

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__rust_route_id__ = route_id
        wrapper.__rust_param_types__ = param_types
        wrapper.__rust_body_schema__ = inferred_schema
        wrapper.__rust_func__ = func

        if method and path:
            _rustcore.register_route(
                method.upper(),
                path,
                route_id,
                param_types,
                inferred_schema,
            )

        return wrapper

    return decorator