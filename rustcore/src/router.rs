// This file handles routing logic in the Rust core.
// It includes functions for matching routes and extracting parameters from requests.

use std::collections::HashMap;

pub struct Route {
    pub method: String,
    pub path: String,
    pub handler_id: String,
}

pub struct Router {
    routes: Vec<Route>,
}

impl Router {
    pub fn new() -> Self {
        Router {
            routes: Vec::new(),
        }
    }

    pub fn add_route(&mut self, method: &str, path: &str, handler_id: &str) {
        self.routes.push(Route {
            method: method.to_string(),
            path: path.to_string(),
            handler_id: handler_id.to_string(),
        });
    }

    pub fn match_route(&self, method: &str, path: &str) -> Option<(&str, HashMap<String, String>)> {
        for route in &self.routes {
            if route.method == method && route.path == path {
                let params = HashMap::new(); // Extract parameters if needed
                return Some((&route.handler_id, params));
            }
        }
        None
    }
}