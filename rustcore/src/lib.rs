pub mod router;
pub mod validation;

use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyList, PyString};
use router::Router;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use validation::{coerce_param, validate_body, CoercedValue};

static GLOBAL_ROUTER: std::sync::LazyLock<Arc<RwLock<Router>>> =
    std::sync::LazyLock::new(|| Arc::new(RwLock::new(Router::new())));

pub fn json_to_py<'py>(py: Python<'py>, val: &serde_json::Value) -> PyResult<Bound<'py, PyAny>> {
    match val {
        serde_json::Value::Null => Ok(py.None().into_bound(py)),
        serde_json::Value::Bool(b) => Ok(PyBool::new(py, *b).to_owned().into_any()),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py)?.into_any())
            } else if let Some(f) = n.as_f64() {
                Ok(PyFloat::new(py, f).into_any())
            } else {
                Ok(py.None().into_bound(py))
            }
        }
        serde_json::Value::String(s) => Ok(PyString::new(py, s).into_any()),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.into_any())
        }
        serde_json::Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            Ok(dict.into_any())
        }
    }
}

pub fn coerced_to_py<'py>(py: Python<'py>, val: &CoercedValue) -> PyResult<Bound<'py, PyAny>> {
    match val {
        CoercedValue::Int(i) => Ok((*i).into_pyobject(py)?.into_any()),
        CoercedValue::Float(f) => Ok(PyFloat::new(py, *f).into_any()),
        CoercedValue::Bool(b) => Ok(PyBool::new(py, *b).to_owned().into_any()),
        CoercedValue::Str(s) => Ok(PyString::new(py, s).into_any()),
    }
}

#[pyfunction]
#[pyo3(signature = (method, path, route_id, param_types=None, body_schema=None))]
pub fn register_route(
    method: &str,
    path: &str,
    route_id: &str,
    param_types: Option<HashMap<String, String>>,
    body_schema: Option<HashMap<String, String>>,
) -> PyResult<()> {
    let mut router = GLOBAL_ROUTER.write().map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {}", e))
    })?;
    router
        .add_route(
            method,
            path,
            route_id,
            param_types.unwrap_or_default(),
            body_schema,
        )
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    Ok(())
}

#[pyfunction]
pub fn clear_routes() -> PyResult<()> {
    let mut router = GLOBAL_ROUTER.write().map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {}", e))
    })?;
    *router = Router::new();
    Ok(())
}

#[pyfunction]
pub fn match_route<'py>(
    py: Python<'py>,
    method: &str,
    path: &str,
) -> PyResult<Option<(String, Bound<'py, PyDict>)>> {
    let router = GLOBAL_ROUTER.read().map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {}", e))
    })?;

    if let Some((meta, raw_params)) = router.match_route(method, path) {
        let params_dict = PyDict::new(py);
        for (k, v) in &raw_params {
            let target_type = meta.param_types.get(k).map(|s| s.as_str()).unwrap_or("str");
            match coerce_param(k, v, target_type) {
                Ok(val) => {
                    params_dict.set_item(k, coerced_to_py(py, &val)?)?;
                }
                Err(_) => {
                    params_dict.set_item(k, PyString::new(py, v))?;
                }
            }
        }
        Ok(Some((meta.route_id.clone(), params_dict)))
    } else {
        Ok(None)
    }
}

#[pyfunction]
#[pyo3(signature = (data, schema=None))]
pub fn validate_input<'py>(
    py: Python<'py>,
    data: Bound<'py, PyAny>,
    schema: Option<HashMap<String, String>>,
) -> PyResult<Bound<'py, PyDict>> {
    let body_bytes: Vec<u8> = if let Ok(bytes) = data.downcast::<PyBytes>() {
        bytes.as_bytes().to_vec()
    } else if let Ok(s) = data.downcast::<PyString>() {
        s.to_str()?.as_bytes().to_vec()
    } else {
        let json_module = py.import("json")?;
        let dumps = json_module.getattr("dumps")?;
        let json_str: Bound<'py, PyString> = dumps.call1((data,))?.extract()?;
        json_str.to_str()?.as_bytes().to_vec()
    };

    let result = validate_body(&body_bytes, schema.as_ref());
    let out = PyDict::new(py);
    out.set_item("ok", result.ok)?;

    if let Some(val) = result.data {
        out.set_item("data", json_to_py(py, &val)?)?;
    }
    if let Some(errs) = result.errors {
        let err_list = PyList::empty(py);
        for e in errs {
            err_list.append(PyString::new(py, &e))?;
        }
        out.set_item("errors", err_list)?;
    }

    Ok(out)
}

#[pyfunction]
#[pyo3(signature = (method, path, _query_string=None, body_bytes=None))]
pub fn handle_request<'py>(
    py: Python<'py>,
    method: &str,
    path: &str,
    _query_string: Option<&str>,
    body_bytes: Option<&[u8]>,
) -> PyResult<Option<(u16, Option<String>, Bound<'py, PyAny>)>> {
    let router = GLOBAL_ROUTER.read().map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {}", e))
    })?;

    let (meta, raw_params) = match router.match_route(method, path) {
        Some(m) => m,
        None => return Ok(None),
    };

    let params_dict = PyDict::new(py);
    let mut validation_errors = Vec::new();

    for (k, v) in &raw_params {
        let target_type = meta.param_types.get(k).map(|s| s.as_str()).unwrap_or("str");
        match coerce_param(k, v, target_type) {
            Ok(coerced) => {
                params_dict.set_item(k, coerced_to_py(py, &coerced)?)?;
            }
            Err(err) => {
                validation_errors.push(err);
            }
        }
    }

    if !validation_errors.is_empty() {
        let err_dict = PyDict::new(py);
        err_dict.set_item("ok", false)?;
        let err_list = PyList::empty(py);
        for e in validation_errors {
            err_list.append(PyString::new(py, &e))?;
        }
        err_dict.set_item("errors", err_list)?;
        return Ok(Some((422, None, err_dict.into_any())));
    }

    if let Some(schema) = &meta.body_schema {
        let bytes = body_bytes.unwrap_or(b"");
        let val_res = validate_body(bytes, Some(schema));
        if !val_res.ok {
            let err_dict = PyDict::new(py);
            err_dict.set_item("ok", false)?;
            let err_list = PyList::empty(py);
            if let Some(errs) = val_res.errors {
                for e in errs {
                    err_list.append(PyString::new(py, &e))?;
                }
            }
            err_dict.set_item("errors", err_list)?;
            return Ok(Some((422, None, err_dict.into_any())));
        }

        if let Some(data) = val_res.data {
            let py_data = json_to_py(py, &data)?;
            params_dict.set_item("__body__", py_data)?;
        }
    } else if let Some(bytes) = body_bytes {
        if !bytes.is_empty() {
            if let Ok(parsed) = serde_json::from_slice::<serde_json::Value>(bytes) {
                let py_data = json_to_py(py, &parsed)?;
                params_dict.set_item("__body__", py_data)?;
            }
        }
    }

    Ok(Some((
        200,
        Some(meta.route_id.clone()),
        params_dict.into_any(),
    )))
}

#[pymodule]
fn _rustcore(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(register_route, m)?)?;
    m.add_function(wrap_pyfunction!(clear_routes, m)?)?;
    m.add_function(wrap_pyfunction!(match_route, m)?)?;
    m.add_function(wrap_pyfunction!(validate_input, m)?)?;
    m.add_function(wrap_pyfunction!(handle_request, m)?)?;
    Ok(())
}