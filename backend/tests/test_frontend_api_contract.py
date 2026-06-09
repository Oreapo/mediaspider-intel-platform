from __future__ import annotations

import ast
import re
from pathlib import Path

from backend.app.main import app


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_API_DIR = ROOT / "frontend" / "src" / "api"
FRONTEND_TYPES = ROOT / "frontend" / "src" / "types.ts"
BACKEND_ROUTES_DIR = ROOT / "backend" / "app" / "api" / "routes"
BACKEND_MAIN = ROOT / "backend" / "app" / "main.py"


def test_frontend_api_calls_match_backend_routes():
    backend_routes = _backend_routes()
    frontend_calls = sorted((method, path) for method, path, _ in _frontend_http_call_specs())

    missing = [
        f"{method.upper()} {path}"
        for method, path in frontend_calls
        if not _matches_backend_route(method, path, backend_routes)
    ]

    assert missing == []


def test_frontend_download_urls_match_backend_routes():
    backend_routes = _backend_routes()
    download_paths = sorted(_frontend_download_paths())

    mismatches = []
    for path in download_paths:
        operation = _matching_backend_operation("get", path, backend_routes)
        if operation is None:
            mismatches.append(f"GET {path}")
            continue
        if "access_token" not in _backend_query_params(operation):
            mismatches.append(f"GET {path}?access_token")

    assert mismatches == []


def test_frontend_literal_query_params_match_backend_routes():
    backend_routes = _backend_routes()
    frontend_calls = sorted(_frontend_http_call_specs())

    missing = []
    for method, path, query_params in frontend_calls:
        if not query_params:
            continue
        operation = _matching_backend_operation(method, path, backend_routes)
        backend_query_params = _backend_query_params(operation or {})
        for query_param in sorted(query_params):
            if query_param not in backend_query_params:
                missing.append(f"{method.upper()} {path}?{query_param}")

    assert missing == []


def test_frontend_filter_interfaces_match_backend_query_params():
    backend_routes = _backend_routes()
    filter_specs = sorted(_frontend_filter_query_specs())

    mismatches = []
    for method, path, interface_name, frontend_fields in filter_specs:
        operation = _matching_backend_operation(method, path, backend_routes)
        backend_query_params = _backend_query_params(operation or {})
        unknown_fields = sorted(frontend_fields - backend_query_params)
        for field in unknown_fields:
            mismatches.append(f"{method.upper()} {path} {interface_name}.{field} is not accepted by backend")

    assert mismatches == []


def test_frontend_payload_interfaces_match_backend_request_bodies():
    backend_routes = _backend_routes()
    payload_specs = sorted(_frontend_payload_specs())

    mismatches = []
    for method, path, interface_name, frontend_fields in payload_specs:
        operation = _matching_backend_operation(method, path, backend_routes)
        if operation is None:
            continue
        body_schema = _request_body_schema(operation)
        if not body_schema:
            mismatches.append(f"{method.upper()} {path} uses {interface_name}, but backend has no JSON body")
            continue

        backend_fields = set(body_schema.get("properties", {}))
        required_fields = set(body_schema.get("required", []))
        unexpected_fields = sorted(frontend_fields - backend_fields)
        missing_required_fields = sorted(required_fields - frontend_fields)

        for field in unexpected_fields:
            mismatches.append(f"{method.upper()} {path} {interface_name}.{field} is not accepted by backend")
        for field in missing_required_fields:
            mismatches.append(f"{method.upper()} {path} {interface_name} is missing required backend field {field}")

    assert mismatches == []


def test_frontend_inline_payloads_match_backend_request_bodies():
    backend_routes = _backend_routes()
    payload_specs = sorted(_frontend_inline_payload_specs())

    mismatches = []
    for method, path, frontend_fields in payload_specs:
        operation = _matching_backend_operation(method, path, backend_routes)
        if operation is None:
            continue
        body_schema = _request_body_schema(operation)
        if not body_schema:
            mismatches.append(f"{method.upper()} {path} sends an inline object, but backend has no JSON body")
            continue

        backend_fields = set(body_schema.get("properties", {}))
        required_fields = set(body_schema.get("required", []))
        unexpected_fields = sorted(frontend_fields - backend_fields)
        missing_required_fields = sorted(required_fields - frontend_fields)

        for field in unexpected_fields:
            mismatches.append(f"{method.upper()} {path} inline payload field {field} is not accepted by backend")
        for field in missing_required_fields:
            mismatches.append(f"{method.upper()} {path} inline payload is missing required backend field {field}")

    assert mismatches == []


def test_frontend_response_envelopes_match_backend_returns():
    backend_response_keys = _backend_literal_response_keys()
    frontend_specs = sorted(_frontend_response_specs())

    mismatches = []
    for method, path, frontend_fields in frontend_specs:
        backend_fields = _matching_backend_response_keys(method, path, backend_response_keys)
        if backend_fields is None:
            continue
        missing_fields = sorted(frontend_fields - backend_fields)
        for field in missing_fields:
            mismatches.append(f"{method.upper()} {path} frontend expects response.{field}, but backend does not return it")

    assert mismatches == []


def test_frontend_response_types_match_backend_response_schemas():
    backend_routes = _backend_routes()
    frontend_specs = sorted(_frontend_response_specs())

    mismatches = []
    for method, path, frontend_fields in frontend_specs:
        operation = _matching_backend_operation(method, path, backend_routes)
        if operation is None:
            continue
        response_schema = _response_schema(operation)
        backend_fields = set(response_schema.get("properties", {}))
        if not backend_fields:
            continue
        missing_fields = sorted(frontend_fields - backend_fields)
        for field in missing_fields:
            mismatches.append(f"{method.upper()} {path} frontend expects response.{field}, but backend schema omits it")

    assert mismatches == []


def _backend_routes() -> dict[str, dict]:
    return app.openapi()["paths"]


def _frontend_http_call_specs() -> set[tuple[str, str, frozenset[str]]]:
    calls: set[tuple[str, str, frozenset[str]]] = set()
    for source in FRONTEND_API_DIR.glob("*.ts"):
        text = source.read_text(encoding="utf-8")
        for method, raw_path in _extract_http_call_paths(text):
            normalized = _normalize_frontend_path(raw_path)
            if normalized:
                calls.add((method, f"/api{normalized}", frozenset(_literal_query_params(raw_path))))
    return calls


def _extract_http_call_paths(text: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    for match in re.finditer(r"http\.(get|post|patch|delete)\b", text):
        method = match.group(1)
        index = _skip_whitespace(text, match.end())
        if index < len(text) and text[index] == "<":
            index = _skip_generic_type(text, index)
        index = _skip_whitespace(text, index)
        if index >= len(text) or text[index] != "(":
            continue
        index = _skip_whitespace(text, index + 1)
        if index >= len(text) or text[index] not in {"'", '"', "`"}:
            continue
        raw_path, _ = _read_quoted_with_end(text, index)
        calls.append((method, raw_path))
    return calls


def _frontend_download_paths() -> set[str]:
    paths: set[str] = set()
    for source in FRONTEND_API_DIR.glob("*.ts"):
        text = source.read_text(encoding="utf-8")
        for raw_path in _extract_api_download_paths(text):
            normalized = _normalize_frontend_path(raw_path)
            if normalized:
                paths.add(f"/api{normalized}")
    return paths


def _extract_api_download_paths(text: str) -> list[str]:
    paths: list[str] = []
    for match in re.finditer(r"\bapiDownloadUrl\s*\(", text):
        index = _skip_whitespace(text, match.end())
        if index >= len(text) or text[index] not in {"'", '"', "`"}:
            continue
        raw_path, _ = _read_quoted_with_end(text, index)
        paths.append(raw_path)
    return paths


def _frontend_response_specs() -> set[tuple[str, str, frozenset[str]]]:
    specs: set[tuple[str, str, frozenset[str]]] = set()
    shared_interfaces = _typescript_interfaces(FRONTEND_TYPES.read_text(encoding="utf-8"))
    for source in FRONTEND_API_DIR.glob("*.ts"):
        text = source.read_text(encoding="utf-8")
        interfaces = shared_interfaces | _typescript_interfaces(text)
        for method, raw_path, response_fields in _extract_http_response_specs(text, interfaces):
            normalized = _normalize_frontend_path(raw_path)
            if normalized and response_fields:
                specs.add((method, f"/api{normalized}", frozenset(response_fields)))
    return specs


def _extract_http_response_specs(text: str, interfaces: dict[str, set[str]]) -> list[tuple[str, str, set[str]]]:
    specs: list[tuple[str, str, set[str]]] = []
    for match in re.finditer(r"http\.(get|post|patch|delete)\b", text):
        method = match.group(1)
        index = _skip_whitespace(text, match.end())
        response_fields: set[str] = set()
        if index < len(text) and text[index] == "<":
            generic_type, index = _read_generic_type(text, index)
            response_fields = _response_type_fields(generic_type, interfaces)
        index = _skip_whitespace(text, index)
        if index >= len(text) or text[index] != "(":
            continue
        index = _skip_whitespace(text, index + 1)
        if index >= len(text) or text[index] not in {"'", '"', "`"}:
            continue
        raw_path, _ = _read_quoted_with_end(text, index)
        specs.append((method, raw_path, response_fields))
    return specs


def _response_type_fields(type_text: str, interfaces: dict[str, set[str]]) -> set[str]:
    inline_fields = _inline_object_type_fields(type_text)
    if inline_fields:
        return inline_fields
    type_name = type_text.strip()
    if re.fullmatch(r"\w+", type_name):
        return interfaces.get(type_name, set())
    return set()


def _inline_object_type_fields(type_text: str) -> set[str]:
    stripped = type_text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return set()
    return set(re.findall(r"\b(\w+)\s*:", stripped))


def _frontend_payload_specs() -> set[tuple[str, str, str, frozenset[str]]]:
    specs: set[tuple[str, str, str, frozenset[str]]] = set()
    for source in FRONTEND_API_DIR.glob("*.ts"):
        text = source.read_text(encoding="utf-8")
        interfaces = _typescript_interfaces(text)
        for body, interface_name in _payload_function_bodies(text):
            if interface_name not in interfaces:
                continue
            for method, raw_path in _extract_payload_http_calls(body):
                normalized = _normalize_frontend_path(raw_path)
                if normalized:
                    specs.add((method, f"/api{normalized}", interface_name, frozenset(interfaces[interface_name])))
    return specs


def _frontend_inline_payload_specs() -> set[tuple[str, str, frozenset[str]]]:
    specs: set[tuple[str, str, frozenset[str]]] = set()
    for source in FRONTEND_API_DIR.glob("*.ts"):
        text = source.read_text(encoding="utf-8")
        for method, raw_path, frontend_fields in _extract_inline_payload_http_calls(text):
            normalized = _normalize_frontend_path(raw_path)
            if normalized and frontend_fields:
                specs.add((method, f"/api{normalized}", frozenset(frontend_fields)))
    return specs


def _frontend_filter_query_specs() -> set[tuple[str, str, str, frozenset[str]]]:
    specs: set[tuple[str, str, str, frozenset[str]]] = set()
    for source in FRONTEND_API_DIR.glob("*.ts"):
        text = source.read_text(encoding="utf-8")
        interfaces = _typescript_interfaces(text)
        for body, interface_name in _filter_query_function_bodies(text):
            if interface_name not in interfaces:
                continue
            for method, raw_path in _extract_http_call_paths(body):
                if method != "get":
                    continue
                normalized = _normalize_frontend_path(raw_path)
                if normalized:
                    specs.add((method, f"/api{normalized}", interface_name, frozenset(interfaces[interface_name])))
    return specs


def _typescript_interfaces(text: str) -> dict[str, set[str]]:
    interfaces: dict[str, set[str]] = {}
    for match in re.finditer(r"export\s+interface\s+(\w+)\s*\{", text):
        body, _ = _read_balanced(text, match.end() - 1, "{", "}")
        interfaces[match.group(1)] = _top_level_type_fields(body)
    return interfaces


def _top_level_type_fields(body: str) -> set[str]:
    fields: set[str] = set()
    depth = 0
    quote: str | None = None
    line_start = True
    index = 0
    while index < len(body):
        char = body[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char in {"{", "[", "("}:
            depth += 1
        elif char in {"}", "]", ")"}:
            depth -= 1
        elif line_start and depth == 0:
            match = re.match(r"\s*(\w+)\??\s*:", body[index:])
            if match:
                fields.add(match.group(1))
        line_start = char == "\n"
        index += 1
    return fields


def _filter_query_function_bodies(text: str) -> list[tuple[str, str]]:
    functions = list(re.finditer(r"export\s+async\s+function\s+\w+\s*\((?P<params>.*?)\)\s*\{", text, re.S))
    bodies: list[tuple[str, str]] = []
    for index, match in enumerate(functions):
        param_match = re.search(r"\b(?:filters|query)\??\s*:\s*(\w+(?:Filters|Query))", match.group("params"))
        if param_match is None:
            continue
        end = functions[index + 1].start() if index + 1 < len(functions) else len(text)
        bodies.append((text[match.end() : end], param_match.group(1)))
    return bodies


def _payload_function_bodies(text: str) -> list[tuple[str, str]]:
    functions = list(re.finditer(r"export\s+async\s+function\s+\w+\s*\((?P<params>.*?)\)\s*\{", text, re.S))
    bodies: list[tuple[str, str]] = []
    for index, match in enumerate(functions):
        param_match = re.search(r"payload\s*:\s*(?:Partial<)?(\w+)>?", match.group("params"))
        if param_match is None:
            continue
        end = functions[index + 1].start() if index + 1 < len(functions) else len(text)
        bodies.append((text[match.end() : end], param_match.group(1)))
    return bodies


def _extract_payload_http_calls(text: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    for match in re.finditer(r"http\.(post|patch)\b", text):
        method = match.group(1)
        index = _skip_whitespace(text, match.end())
        if index < len(text) and text[index] == "<":
            index = _skip_generic_type(text, index)
        index = _skip_whitespace(text, index)
        if index >= len(text) or text[index] != "(":
            continue
        index = _skip_whitespace(text, index + 1)
        if index >= len(text) or text[index] not in {"'", '"', "`"}:
            continue
        raw_path, end = _read_quoted_with_end(text, index)
        if re.search(r",\s*payload\b", text[end : end + 300]):
            calls.append((method, raw_path))
    return calls


def _extract_inline_payload_http_calls(text: str) -> list[tuple[str, str, set[str]]]:
    calls: list[tuple[str, str, set[str]]] = []
    for match in re.finditer(r"http\.(post|patch)\b", text):
        method = match.group(1)
        index = _skip_whitespace(text, match.end())
        if index < len(text) and text[index] == "<":
            index = _skip_generic_type(text, index)
        index = _skip_whitespace(text, index)
        if index >= len(text) or text[index] != "(":
            continue
        index = _skip_whitespace(text, index + 1)
        if index >= len(text) or text[index] not in {"'", '"', "`"}:
            continue
        raw_path, index = _read_quoted_with_end(text, index)
        index = _skip_whitespace(text, index)
        if index >= len(text) or text[index] != ",":
            continue
        index = _skip_whitespace(text, index + 1)
        if index >= len(text) or text[index] != "{":
            continue
        object_body, _ = _read_balanced(text, index, "{", "}")
        fields = _object_literal_fields(object_body)
        if fields:
            calls.append((method, raw_path, fields))
    return calls


def _object_literal_fields(object_body: str) -> set[str]:
    fields: set[str] = set()
    for part in _split_top_level_commas(object_body):
        item = part.strip()
        if not item or item.startswith("..."):
            continue
        match = re.match(r"(\w+)\s*(?::|$)", item)
        if match:
            fields.add(match.group(1))
    return fields


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"{": 0, "[": 0, "(": 0}
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char in depths:
            depths[char] += 1
        elif char == "}":
            depths["{"] -= 1
        elif char == "]":
            depths["["] -= 1
        elif char == ")":
            depths["("] -= 1
        elif char == "," and all(depth == 0 for depth in depths.values()):
            parts.append(text[start:index])
            start = index + 1
        index += 1
    parts.append(text[start:])
    return parts


def _normalize_frontend_path(raw_path: str) -> str:
    output = []
    index = 0
    while index < len(raw_path):
        if raw_path.startswith("${", index):
            end = raw_path.find("}", index + 2)
            if end == -1:
                break
            if output and output[-1] == "/":
                output.append("{param}")
            index = end + 1
            continue
        output.append(raw_path[index])
        index += 1

    path = "".join(output).split("?", 1)[0]
    while path.endswith("{param}") and path.count("/") == 1:
        path = path[: -len("{param}")]
    return path.rstrip("/") or "/"


def _literal_query_params(raw_path: str) -> set[str]:
    if "?" not in raw_path:
        return set()
    query = raw_path.split("?", 1)[1]
    return {
        item.split("=", 1)[0]
        for item in query.split("&")
        if item and not item.startswith("${") and item.split("=", 1)[0]
    }


def _matches_backend_route(frontend_method: str, frontend_path: str, backend_routes: dict[str, dict]) -> bool:
    return _matching_backend_operation(frontend_method, frontend_path, backend_routes) is not None


def _matching_backend_operation(frontend_method: str, frontend_path: str, backend_routes: dict[str, dict]) -> dict | None:
    frontend_segments = frontend_path.strip("/").split("/")
    for backend_path, operations in backend_routes.items():
        if frontend_method not in operations:
            continue
        backend_segments = backend_path.strip("/").split("/")
        if len(frontend_segments) != len(backend_segments):
            continue
        if all(_segments_match(frontend, backend) for frontend, backend in zip(frontend_segments, backend_segments)):
            return operations[frontend_method]
    return None


def _backend_literal_response_keys() -> dict[tuple[str, str], set[str]]:
    routes: dict[tuple[str, str], set[str]] = {}
    for source in [*BACKEND_ROUTES_DIR.glob("*.py"), BACKEND_MAIN]:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        router_prefix = _router_prefix(tree)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            response_keys = _literal_return_keys(node)
            if not response_keys:
                continue
            for owner, method, route_path in _route_decorators(node):
                if owner == "router":
                    path = _join_route_path("/api", router_prefix, route_path)
                else:
                    path = _join_route_path(route_path)
                routes[(method, path)] = response_keys
    return routes


def _router_prefix(tree: ast.Module) -> str:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                return keyword.value.value
    return ""


def _route_decorators(node: ast.FunctionDef) -> list[tuple[str, str, str]]:
    routes: list[tuple[str, str, str]] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Attribute):
            continue
        if not isinstance(decorator.func.value, ast.Name):
            continue
        owner = decorator.func.value.id
        if owner not in {"router", "app"}:
            continue
        method = decorator.func.attr
        if method not in {"get", "post", "patch", "delete"}:
            continue
        route_path = ""
        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
            route_path = decorator.args[0].value
        routes.append((owner, method, route_path))
    return routes


def _literal_return_keys(node: ast.FunctionDef) -> set[str]:
    keys: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Return) or not isinstance(child.value, ast.Dict):
            continue
        for key in child.value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
    return keys


def _join_route_path(*parts: str) -> str:
    path = "".join(parts)
    return re.sub(r"/+", "/", path) or "/"


def _matching_backend_response_keys(
    frontend_method: str,
    frontend_path: str,
    backend_response_keys: dict[tuple[str, str], set[str]],
) -> set[str] | None:
    frontend_segments = frontend_path.strip("/").split("/")
    for (backend_method, backend_path), response_keys in backend_response_keys.items():
        if frontend_method != backend_method:
            continue
        backend_segments = backend_path.strip("/").split("/")
        if len(frontend_segments) != len(backend_segments):
            continue
        if all(_segments_match(frontend, backend) for frontend, backend in zip(frontend_segments, backend_segments)):
            return response_keys
    return None


def _backend_query_params(operation: dict) -> set[str]:
    return {
        parameter["name"]
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "query"
    }


def _request_body_schema(operation: dict) -> dict:
    schema = (
        operation.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    return _resolve_schema(schema)


def _response_schema(operation: dict) -> dict:
    content = operation.get("responses", {}).get("200", {}).get("content", {})
    schema = content.get("application/json", {}).get("schema", {})
    return _resolve_schema(schema)


def _resolve_schema(schema: dict) -> dict:
    if "$ref" not in schema:
        if "anyOf" in schema:
            for option in schema["anyOf"]:
                resolved = _resolve_schema(option)
                if resolved.get("properties"):
                    return resolved
        if "items" in schema:
            return _resolve_schema(schema["items"])
        return schema
    schema_name = schema["$ref"].rsplit("/", 1)[-1]
    return app.openapi()["components"]["schemas"].get(schema_name, {})


def _segments_match(frontend: str, backend: str) -> bool:
    if frontend == backend:
        return True
    return frontend.startswith("{") and backend.startswith("{")


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _skip_generic_type(text: str, index: int) -> int:
    _, end = _read_generic_type(text, index)
    return end


def _read_generic_type(text: str, index: int) -> tuple[str, int]:
    depth = 0
    start = index + 1
    while index < len(text):
        if text[index] == "<":
            depth += 1
        elif text[index] == ">":
            depth -= 1
            if depth == 0:
                return text[start:index], index + 1
        index += 1
    return text[start:index], index


def _read_balanced(text: str, index: int, opening: str, closing: str) -> tuple[str, int]:
    depth = 0
    start = index + 1
    quote: str | None = None
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start:index], index + 1
        index += 1
    return text[start:index], index


def _read_quoted(text: str, index: int) -> str:
    value, _ = _read_quoted_with_end(text, index)
    return value


def _read_quoted_with_end(text: str, index: int) -> tuple[str, int]:
    quote = text[index]
    index += 1
    chars = []
    while index < len(text):
        char = text[index]
        if char == "\\":
            chars.append(char)
            if index + 1 < len(text):
                chars.append(text[index + 1])
            index += 2
            continue
        if char == quote:
            break
        chars.append(char)
        index += 1
    return "".join(chars), index + 1
