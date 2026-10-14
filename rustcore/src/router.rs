use matchit::Router as MatchitRouter;
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct RouteMetadata {
    pub route_id: String,
    pub path: String,
    pub method: String,
    pub param_types: HashMap<String, String>,
    pub body_schema: Option<HashMap<String, String>>,
}

#[derive(Default)]
pub struct Router {
    methods: HashMap<String, MatchitRouter<RouteMetadata>>,
    routes: HashMap<String, Vec<RouteMetadata>>,
}

impl Router {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_route(
        &mut self,
        method: &str,
        path: &str,
        route_id: &str,
        param_types: HashMap<String, String>,
        body_schema: Option<HashMap<String, String>>,
    ) -> Result<(), String> {
        let normalized_path = normalize_path(path);
        let method_upper = method.to_uppercase();

        let meta = RouteMetadata {
            route_id: route_id.to_string(),
            path: normalized_path.clone(),
            method: method_upper.clone(),
            param_types,
            body_schema,
        };

        let route_list = self.routes.entry(method_upper.clone()).or_default();
        if let Some(pos) = route_list.iter().position(|r| r.path == normalized_path) {
            route_list[pos] = meta;
        } else {
            route_list.push(meta);
        }

        let mut new_router = MatchitRouter::new();
        for r in route_list {
            new_router
                .insert(&r.path, r.clone())
                .map_err(|e| e.to_string())?;
        }
        self.methods.insert(method_upper, new_router);

        Ok(())
    }

    pub fn match_route<'a>(
        &'a self,
        method: &str,
        path: &str,
    ) -> Option<(&'a RouteMetadata, HashMap<String, String>)> {
        let method_upper = method.to_uppercase();
        let router = self.methods.get(&method_upper)?;
        let normalized = normalize_path(path);

        match router.at(&normalized) {
            Ok(matched) => {
                let mut params = HashMap::new();
                for (k, v) in matched.params.iter() {
                    params.insert(k.to_string(), v.to_string());
                }
                Some((matched.value, params))
            }
            Err(_) => None,
        }
    }
}

pub fn normalize_path(path: &str) -> String {
    if path.is_empty() {
        return "/".to_string();
    }
    let trimmed = path.trim();
    if trimmed.len() > 1 && trimmed.ends_with('/') {
        trimmed.trim_end_matches('/').to_string()
    } else {
        trimmed.to_string()
    }
}