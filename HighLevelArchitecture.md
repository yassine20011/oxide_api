# oxide_api - High-Performance FastAPI Router

## Architecture Overview

```
┌─────────────────────────────┐
│        Developer            │
│   Writes FastAPI handlers   │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐  🐍 Python Layer
│      FastAPI Wrapper       │
│ • Receives HTTP requests    │
│ • Calls into Rust core      │
│ • Invokes Python handler    │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐  🦀 High-performance Layer
│        Rust Core           │
│ • Matches route            │
│ • Extracts path/query/body │
│ • Validates input data     │
│ • Returns sanitized output │
└─────────────────────────────┘
```

## Python Integration Layer

The Python layer maintains FastAPI compatibility while leveraging Rust performance through custom decorators:

```python
@app.get("/users/{user_id}")
@rust_route("get_user")  # Points to Rust route ID
def get_user_handler(user_id: int):
    # Your handler logic here
    pass
```

### Decorator Responsibilities:

- Register route + schema with Rust core
- Delegate routing + validation to Rust on each request
- Bridge between Rust results and Python handlers

## 🔄 Runtime Request Flow

### Basic Routing Flow

```
User Request (GET /users/123)
        ↓
FastAPI receives request
        ↓
Call Rust: match_route("GET", "/users/123")
        ↓
Rust returns: ("get_user", {"user_id": 123})
        ↓
FastAPI calls: handler(**params)
```

### Body Validation Flow

```
Body validation (POST /users)
        ↓
FastAPI reads JSON
        ↓
Rust validates using compiled schema
        ↓
Returns typed & safe data (or validation error)
```

## 🧪 MVP Scope (v0.1)

| Feature                        | MVP? | Rust | Python                |
| ------------------------------ | ---- | ---- | --------------------- |
| Basic routing (GET /foo/{bar}) | ✅   | ✅   | ✅                    |
| Path param extraction          | ✅   | ✅   | ✅                    |
| Simple validation (e.g., int)  | ✅   | ✅   | ✅                    |
| Calling handlers from match ID | ✅   | ✅   | ✅                    |
| Error handling (404, 422)      | ✅   | ✅   | ✅                    |
| Schema registration (advanced) | ❌   | -    | Later                 |
| OpenAPI generation             | ❌   | -    | ✅ (FastAPI fallback) |

## Project Structure

```
oxide_api/
├── rustcore/                 
│   ├── src/
│   │   ├── lib.rs
│   │   ├── router.rs
│   │   └── validation.rs
│   └── Cargo.toml
├── pyoxide_api/              # Python bridge
│   ├── __init__.py
│   ├── decorators.py
│   └── core.py
├── examples/
│   └── user_api.py           # FastAPI example using Rust core
├── tests/
│   ├── test_rust_core.rs
│   └── test_python_integration.py
├── README.md
├── pyproject.toml            # For maturin build
└── Cargo.toml
```

## Data Exchange (Rust <=> Python)

### Successful Path Match

```json
{
  "route_id": "get_user",
  "params": {
    "user_id": 123
  }
}
```

### Successful Validation

```json
{
  "ok": true,
  "data": {
    "name": "Alice",
    "age": 30
  }
}
```

### Validation Error

```json
{
  "ok": false,
  "errors": [
    "Missing required field: 'name'",
    "Field 'age' must be a positive integer"
  ]
}
```

## Getting Started

### Installation

```bash
pip install oxide_api
```

### Basic Usage

```python
from fastapi import FastAPI
from oxide_api import rust_route

app = FastAPI()

@app.get("/users/{user_id}")
@rust_route("get_user")
def get_user(user_id: int):
    return {"user_id": user_id, "name": "Alice"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Performance Goals

- **Route matching**: 10-100x faster than pure Python
- **Validation**: 5-50x faster for complex schemas
- **Memory usage**: Minimal overhead over standard FastAPI
- **Compatibility**: 100% FastAPI decorator compatibility
