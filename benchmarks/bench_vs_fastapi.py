import asyncio
import time
from typing import Any, Callable, Dict, Tuple
from fastapi import FastAPI
from pydantic import BaseModel
from oxide_api import rust_route
from oxide_api.core import _original_fastapi_call

ITERATIONS = 20000
WARMUP = 1000

class AsgiBenchHarness:
    def __init__(self, app_call: Callable, scope: Dict[str, Any], body: bytes = b""):
        self.app_call = app_call
        self.scope = scope
        self.recv_event = {"type": "http.request", "body": body, "more_body": False}

    async def receive(self):
        return self.recv_event

    async def send(self, message):
        pass

    async def run(self, count: int) -> Tuple[float, float]:
        call = self.app_call
        scope = self.scope
        recv = self.receive
        send = self.send

        for _ in range(WARMUP):
            await call(scope, recv, send)

        t0 = time.perf_counter()
        for _ in range(count):
            await call(scope, recv, send)
        t1 = time.perf_counter()

        elapsed = t1 - t0
        req_sec = count / elapsed
        us_per_req = (elapsed / count) * 1_000_000
        return req_sec, us_per_req

class UserModel(BaseModel):
    name: str
    age: int

def setup_apps():
    vanilla_app = FastAPI()
    oxide_app = FastAPI()

    @vanilla_app.get("/users/{user_id}")
    def vanilla_get_user(user_id: int):
        return {"user_id": user_id, "name": "Alice"}

    @oxide_app.get("/users/{user_id}")
    @rust_route("bench_get_user")
    def oxide_get_user(user_id: int):
        return {"user_id": user_id, "name": "Alice"}

    @vanilla_app.post("/users")
    def vanilla_create_user(user: UserModel):
        return {"message": "User created", "user": {"name": user.name, "age": user.age}}

    @oxide_app.post("/users")
    @rust_route("bench_create_user", schema={"name": "str", "age": "int"})
    def oxide_create_user(user: dict):
        return {"message": "User created", "user": user}

    vanilla_scale_app = FastAPI()
    oxide_scale_app = FastAPI()

    for i in range(250):
        path = f"/api/v1/resource_{i}/{{id}}"

        def make_vanilla_endpoint(idx):
            def endpoint(id: int):
                return {"resource": idx, "id": id}
            return endpoint

        def make_oxide_endpoint(idx):
            @rust_route(f"scale_res_{idx}")
            def endpoint(id: int):
                return {"resource": idx, "id": id}
            return endpoint

        vanilla_scale_app.add_api_route(path, make_vanilla_endpoint(i), methods=["GET"])
        oxide_scale_app.add_api_route(path, make_oxide_endpoint(i), methods=["GET"])

    return (
        vanilla_app,
        oxide_app,
        vanilla_scale_app,
        oxide_scale_app,
    )

def make_scope(method: str, path: str, body_len: int = 0) -> Dict[str, Any]:
    headers = []
    if body_len > 0:
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(body_len).encode("latin-1")),
        ]
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
    }

async def run_all_benchmarks():
    vanilla_app, oxide_app, vanilla_scale, oxide_scale = setup_apps()

    vanilla_call = lambda s, r, w: _original_fastapi_call(vanilla_app, s, r, w)
    oxide_call = lambda s, r, w: oxide_app(s, r, w)
    vanilla_scale_call = lambda s, r, w: _original_fastapi_call(vanilla_scale, s, r, w)
    oxide_scale_call = lambda s, r, w: oxide_scale(s, r, w)

    scenarios = [
        (
            "1. Simple Path Param (GET /users/42)",
            make_scope("GET", "/users/42"),
            b"",
            vanilla_call,
            oxide_call,
        ),
        (
            "2. Route Scaling (Route 250 of 250)",
            make_scope("GET", "/api/v1/resource_249/42"),
            b"",
            vanilla_scale_call,
            oxide_scale_call,
        ),
        (
            "3. JSON Body Validation (POST /users)",
            make_scope("POST", "/users", len(b'{"name":"Bob","age":25}')),
            b'{"name":"Bob","age":25}',
            vanilla_call,
            oxide_call,
        ),
        (
            "4. Fast-Fail 422 Error (GET /users/not_an_int)",
            make_scope("GET", "/users/not_an_int"),
            b"",
            vanilla_call,
            oxide_call,
        ),
        (
            "5. 404 Route Not Found (GET /api/v1/nonexistent/path)",
            make_scope("GET", "/api/v1/nonexistent/path"),
            b"",
            vanilla_scale_call,
            oxide_scale_call,
        ),
    ]

    results = []

    print(f"Running benchmarks ({ITERATIONS:,} iterations per scenario after {WARMUP:,} warmup)...")
    print("-" * 80)

    for name, scope, body, v_call, o_call in scenarios:
        print(f"Benchmarking: {name}...")
        v_harness = AsgiBenchHarness(v_call, scope, body)
        v_rps, v_us = await v_harness.run(ITERATIONS)

        o_harness = AsgiBenchHarness(o_call, scope, body)
        o_rps, o_us = await o_harness.run(ITERATIONS)

        speedup = o_rps / v_rps
        results.append((name, v_rps, v_us, o_rps, o_us, speedup))

    print("\n" + "=" * 105)
    print(f"{'Scenario Name':<42} | {'Vanilla FastAPI':<22} | {'oxide_api':<22} | {'Speedup'}")
    print(f"{'':<42} | {'req/sec':<10} {'µs/req':<10} | {'req/sec':<10} {'µs/req':<10} |")
    print("-" * 105)

    for name, v_rps, v_us, o_rps, o_us, speedup in results:
        print(
            f"{name:<42} | {v_rps:>8.0f}/s {v_us:>8.2f}µs | {o_rps:>8.0f}/s {o_us:>8.2f}µs | {speedup:>6.2f}x faster"
        )
    print("=" * 105 + "\n")

    return results

if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
