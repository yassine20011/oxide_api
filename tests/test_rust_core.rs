#[cfg(test)]
mod tests {
    use _rustcore::router::Router;
    use _rustcore::validation::{coerce_param, validate_body, validate_path_params, CoercedValue};
    use std::collections::HashMap;

    #[test]
    fn test_route_matching() {
        let mut router = Router::new();
        let mut param_types = HashMap::new();
        param_types.insert("user_id".to_string(), "int".to_string());

        let res = router.add_route("GET", "/users/{user_id}", "get_user", param_types, None);
        assert!(res.is_ok());

        let matched = router.match_route("GET", "/users/123");
        assert!(matched.is_some());
        let (meta, params) = matched.unwrap();
        assert_eq!(meta.route_id, "get_user");
        assert_eq!(params.get("user_id"), Some(&"123".to_string()));
    }

    #[test]
    fn test_param_extraction() {
        let mut router = Router::new();
        let res = router.add_route("GET", "/foo/{bar}", "get_foo", HashMap::new(), None);
        assert!(res.is_ok());

        let matched = router.match_route("GET", "/foo/baz");
        assert!(matched.is_some());
        let (meta, params) = matched.unwrap();
        assert_eq!(meta.route_id, "get_foo");
        assert_eq!(params.get("bar"), Some(&"baz".to_string()));
    }

    #[test]
    fn test_route_not_found() {
        let mut router = Router::new();
        let _ = router.add_route("GET", "/users/{user_id}", "get_user", HashMap::new(), None);
        let matched = router.match_route("GET", "/nonexistent");
        assert!(matched.is_none());
    }

    #[test]
    fn test_validation_success() {
        let coerced = coerce_param("user_id", "123", "int");
        assert_eq!(coerced, Ok(CoercedValue::Int(123)));

        let mut raw_params = HashMap::new();
        raw_params.insert("user_id".to_string(), "123".to_string());
        let mut types = HashMap::new();
        types.insert("user_id".to_string(), "int".to_string());

        let valid_params = validate_path_params(&raw_params, &types);
        assert!(valid_params.is_ok());

        let mut schema = HashMap::new();
        schema.insert("name".to_string(), "str".to_string());
        schema.insert("age".to_string(), "int".to_string());

        let body = br#"{"name": "Alice", "age": 30}"#;
        let res = validate_body(body, Some(&schema));
        assert!(res.ok);
        assert!(res.data.is_some());
        assert!(res.errors.is_none());
    }

    #[test]
    fn test_validation_failure() {
        let coerced = coerce_param("user_id", "invalid_int", "int");
        assert!(coerced.is_err());
        assert_eq!(
            coerced.unwrap_err(),
            "Field 'user_id' must be an integer"
        );

        let mut schema = HashMap::new();
        schema.insert("name".to_string(), "str".to_string());
        schema.insert("age".to_string(), "int".to_string());

        let body_missing_name = br#"{"age": 30}"#;
        let res1 = validate_body(body_missing_name, Some(&schema));
        assert!(!res1.ok);
        let errs1 = res1.errors.unwrap();
        assert!(errs1.iter().any(|e| e == "Missing required field: 'name'"));

        let body_negative_age = br#"{"name": "Alice", "age": -5}"#;
        let res2 = validate_body(body_negative_age, Some(&schema));
        assert!(!res2.ok);
        let errs2 = res2.errors.unwrap();
        assert!(errs2.iter().any(|e| e == "Field 'age' must be a positive integer"));
    }
}