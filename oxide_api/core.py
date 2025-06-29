from fastapi import FastAPI
from rustcore import match_route, validate_input

app = FastAPI()

@app.middleware("http")
async def rust_middleware(request, call_next):
    # Match the route using Rust core
    route_info = match_route(request.method, request.url.path)
    
    if route_info is None:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    
    route_id, params = route_info
    request.state.route_id = route_id
    request.state.params = params

    response = await call_next(request)
    return response

def validate_request_body(body):
    validation_result = validate_input(body)
    if not validation_result["ok"]:
        raise HTTPException(status_code=422, detail=validation_result["errors"])
    return validation_result["data"]