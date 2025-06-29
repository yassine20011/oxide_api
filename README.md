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

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests to improve the project.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.