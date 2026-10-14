# oxide_api - FastAPI with Rust Integration

## Overview

The `oxide_api` project is a high-performance web API framework that combines the ease of use of FastAPI with the speed and efficiency of Rust. This project aims to provide a seamless integration between Python and Rust, allowing developers to leverage Rust's performance for routing and validation while maintaining the simplicity of FastAPI for building web applications.

## Features

- **High Performance**: Rust core for routing and validation, significantly faster than pure Python implementations.
- **FastAPI Compatibility**: Fully compatible with FastAPI decorators and features.
- **Type Safety**: Rust's strong typing ensures safe and reliable data handling.
- **Custom Decorators**: Easy-to-use decorators for integrating Rust functionality into FastAPI routes.

## Project Structure

```
oxide_api/
├── rustcore/                 # Rust library (crate)
│   ├── src/
│   │   ├── lib.rs            # Main library file
│   │   ├── router.rs         # Routing logic
│   │   └── validation.rs      # Input validation
│   └── Cargo.toml            # Rust project configuration
├── oxide_api/                # Python bridge
│   ├── __init__.py           # Package initialization
│   ├── decorators.py          # Custom decorators for Rust integration
│   └── core.py               # Core logic for Python integration
├── examples/                 # Example applications
│   └── user_api.py           # FastAPI example using Rust core
├── tests/                    # Test suite
│   ├── test_rust_core.rs     # Unit tests for Rust core
│   └── test_python_integration.py # Unit tests for Python integration
├── pyproject.toml            # Python project configuration
├── Cargo.toml                # Root-level Rust project configuration
└── README.md                 # Project documentation
```

## Getting Started

### Installation

To install the `oxide_api` package, run:

```bash
pip install oxide_api
```

### Basic Usage

Here is a simple example of how to use the `oxide_api` package with FastAPI:

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

## Benchmarks (v0.1 MVP)

Direct ASGI framework benchmarks (20,000 iterations per scenario after 1,000 warmup iterations) comparing Vanilla FastAPI against `oxide_api`:

| Scenario Name | Vanilla FastAPI | `oxide_api` | Speedup |
| :--- | :---: | :---: | :---: |
| **1. Simple Path Param (`GET /users/42`)** | 2,789 req/s (358.56 µs) | **163,249 req/s (6.13 µs)** | **58.53x faster** |
| **2. Route Scaling (Route 250 of 250)** | 1,266 req/s (790.07 µs) | **199,828 req/s (5.00 µs)** | **157.88x faster** |
| **3. JSON Body Validation (`POST /users`)** | 2,473 req/s (404.31 µs) | **148,412 req/s (6.74 µs)** | **60.00x faster** |
| **4. Fast-Fail 422 Error (`GET /users/not_an_int`)** | 5,606 req/s (178.38 µs) | **187,764 req/s (5.33 µs)** | **33.49x faster** |
| **5. 404 Route Not Found (`GET /api/v1/nonexistent/path`)** | 1,219 req/s (820.32 µs) | **573,509 req/s (1.74 µs)** | **470.46x faster** |

### Running the Benchmark Suite

To run the reproducible benchmark suite:

```bash
python benchmarks/bench_vs_fastapi.py
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests to improve the project.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.