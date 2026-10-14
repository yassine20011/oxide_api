use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum CoercedValue {
    Int(i64),
    Float(f64),
    Bool(bool),
    Str(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub errors: Option<Vec<String>>,
}

pub fn coerce_param(name: &str, raw_val: &str, target_type: &str) -> Result<CoercedValue, String> {
    match target_type.to_lowercase().as_str() {
        "int" | "integer" | "i64" | "i32" => raw_val
            .parse::<i64>()
            .map(CoercedValue::Int)
            .map_err(|_| format!("Field '{}' must be an integer", name)),
        "float" | "f64" | "f32" => raw_val
            .parse::<f64>()
            .map(CoercedValue::Float)
            .map_err(|_| format!("Field '{}' must be a float", name)),
        "bool" | "boolean" => match raw_val.to_lowercase().as_str() {
            "true" | "1" => Ok(CoercedValue::Bool(true)),
            "false" | "0" => Ok(CoercedValue::Bool(false)),
            _ => Err(format!("Field '{}' must be a boolean", name)),
        },
        _ => Ok(CoercedValue::Str(raw_val.to_string())),
    }
}

pub fn validate_path_params(
    raw_params: &HashMap<String, String>,
    param_types: &HashMap<String, String>,
) -> Result<HashMap<String, CoercedValue>, Vec<String>> {
    let mut coerced = HashMap::new();
    let mut errors = Vec::new();

    for (k, v) in raw_params {
        let target_type = param_types.get(k).map(|s| s.as_str()).unwrap_or("str");
        match coerce_param(k, v, target_type) {
            Ok(val) => {
                coerced.insert(k.clone(), val);
            }
            Err(err) => errors.push(err),
        }
    }

    if errors.is_empty() {
        Ok(coerced)
    } else {
        Err(errors)
    }
}

pub fn validate_body(
    body_bytes: &[u8],
    schema: Option<&HashMap<String, String>>,
) -> ValidationResult {
    let parsed: Value = match serde_json::from_slice(body_bytes) {
        Ok(v) => v,
        Err(_) => {
            return ValidationResult {
                ok: false,
                data: None,
                errors: Some(vec!["Invalid JSON payload".to_string()]),
            };
        }
    };

    let schema_map = match schema {
        Some(s) if !s.is_empty() => s,
        _ => {
            return ValidationResult {
                ok: true,
                data: Some(parsed),
                errors: None,
            };
        }
    };

    let obj = match parsed.as_object() {
        Some(o) => o,
        None => {
            return ValidationResult {
                ok: false,
                data: None,
                errors: Some(vec!["Body must be a JSON object".to_string()]),
            };
        }
    };

    let mut errors = Vec::new();

    for (field_name, field_type) in schema_map {
        match obj.get(field_name) {
            None => {
                errors.push(format!("Missing required field: '{}'", field_name));
            }
            Some(val) => {
                match field_type.to_lowercase().as_str() {
                    "str" | "string" if !val.is_string() => {
                        errors.push(format!("Field '{}' must be a string", field_name));
                    }
                    "int" | "integer" | "i64" | "i32" => {
                        if let Some(i) = val.as_i64() {
                            if field_name == "age" && i <= 0 {
                                errors.push("Field 'age' must be a positive integer".to_string());
                            }
                        } else {
                            errors.push(format!("Field '{}' must be an integer", field_name));
                        }
                    }
                    "float" | "number" if !val.is_number() => {
                        errors.push(format!("Field '{}' must be a number", field_name));
                    }
                    "bool" | "boolean" if !val.is_boolean() => {
                        errors.push(format!("Field '{}' must be a boolean", field_name));
                    }
                    "dict" | "object" if !val.is_object() => {
                        errors.push(format!("Field '{}' must be an object", field_name));
                    }
                    "list" | "array" if !val.is_array() => {
                        errors.push(format!("Field '{}' must be an array", field_name));
                    }
                    _ => {}
                }
            }
        }
    }

    if errors.is_empty() {
        ValidationResult {
            ok: true,
            data: Some(parsed),
            errors: None,
        }
    } else {
        ValidationResult {
            ok: false,
            data: None,
            errors: Some(errors),
        }
    }
}