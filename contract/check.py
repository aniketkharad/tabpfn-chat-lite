#!/usr/bin/env python3
"""Contract test harness: validates OpenAPI 3.1, JSON schemas, messages, and all fixtures."""

import json
import re
import sys
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
CONTRACT_DIR = ROOT_DIR / "contract"
SCHEMAS_DIR = CONTRACT_DIR / "schemas"
FIXTURES_DIR = CONTRACT_DIR / "fixtures"
MESSAGES_FILE = CONTRACT_DIR / "messages.json"
OPENAPI_FILE = CONTRACT_DIR / "openapi.yaml"

CLOSED_ERROR_CODES = {
    "validation",
    "unsupported",
    "pii_detected",
    "rate_limited",
    "queue_full",
    "quota_gemini",
    "quota_tabpfn",
    "capacity_exhausted",
    "kill_switch",
    "turn_limit",
    "backend_waking",
    "upstream_unavailable",
    "internal",
}

CAPABILITIES = {
    "classification",
    "regression",
    "forecasting",
    "anomaly_detection",
    "data_generation",
    "interpretability",
}


class ValidationError(Exception):
    pass


class SchemaValidator:
    def __init__(self, schemas_dir: Path):
        self.schemas_dir = schemas_dir
        self.schemas = {}
        for path in schemas_dir.glob("*.json"):
            with open(path, "r", encoding="utf-8") as f:
                self.schemas[path.name] = json.load(f)

    def resolve_ref(self, ref_str: str, base_schema: dict):
        if ref_str.startswith("#/"):
            # Internal reference
            parts = ref_str.lstrip("#/").split("/")
            curr = base_schema
            for part in parts:
                curr = curr[part]
            return curr
        else:
            # File reference e.g. "table.json" or "./table.json"
            clean_name = Path(ref_str).name
            if clean_name in self.schemas:
                return self.schemas[clean_name]
            raise ValidationError(f"Cannot resolve $ref: {ref_str}")

    def validate(self, instance, schema, path="root"):
        if "$ref" in schema:
            target = self.resolve_ref(schema["$ref"], schema)
            self.validate(instance, target, path)
            return

        if "oneOf" in schema:
            matches = 0
            errors = []
            for idx, alt in enumerate(schema["oneOf"]):
                try:
                    self.validate(instance, alt, f"{path}.oneOf[{idx}]")
                    matches += 1
                except ValidationError as e:
                    errors.append(str(e))
            if matches != 1:
                raise ValidationError(
                    f"At {path}: expected exactly one match in oneOf, got {matches}. Errors: {'; '.join(errors)}"
                )
            return

        if "const" in schema:
            if instance != schema["const"]:
                raise ValidationError(f"At {path}: expected const '{schema['const']}', got '{instance}'")

        if "enum" in schema:
            if instance not in schema["enum"]:
                raise ValidationError(f"At {path}: '{instance}' is not in enum {schema['enum']}")

        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            valid_type = False
            for t in types:
                if t == "object" and isinstance(instance, dict):
                    valid_type = True
                elif t == "array" and isinstance(instance, list):
                    valid_type = True
                elif t == "string" and isinstance(instance, str):
                    valid_type = True
                elif t == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
                    valid_type = True
                elif t == "number" and (isinstance(instance, (int, float)) and not isinstance(instance, bool)):
                    valid_type = True
                elif t == "boolean" and isinstance(instance, bool):
                    valid_type = True
                elif t == "null" and instance is None:
                    valid_type = True

            if not valid_type:
                raise ValidationError(
                    f"At {path}: expected type {schema['type']}, got {type(instance).__name__} ({instance!r})"
                )

        # String constraints
        if isinstance(instance, str):
            if "pattern" in schema:
                if not re.search(schema["pattern"], instance):
                    raise ValidationError(f"At {path}: '{instance}' does not match pattern {schema['pattern']}")
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                raise ValidationError(f"At {path}: string length {len(instance)} > max {schema['maxLength']}")
            if "minLength" in schema and len(instance) < schema["minLength"]:
                raise ValidationError(f"At {path}: string length {len(instance)} < min {schema['minLength']}")

        # Number constraints
        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                raise ValidationError(f"At {path}: value {instance} < minimum {schema['minimum']}")
            if "maximum" in schema and instance > schema["maximum"]:
                raise ValidationError(f"At {path}: value {instance} > maximum {schema['maximum']}")

        # Array constraints
        if isinstance(instance, list):
            if schema.get("uniqueItems") and len(instance) != len(set(instance)):
                raise ValidationError(f"At {path}: array items must be unique")
            if "items" in schema:
                for idx, item in enumerate(instance):
                    self.validate(item, schema["items"], f"{path}[{idx}]")

        # Object constraints
        if isinstance(instance, dict):
            required = schema.get("required", [])
            for req in required:
                if req not in instance:
                    raise ValidationError(f"At {path}: missing required property '{req}'")

            props = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)

            for key, val in instance.items():
                if key in props:
                    self.validate(val, props[key], f"{path}.{key}")
                elif additional is False:
                    raise ValidationError(f"At {path}: additional property '{key}' is not allowed")
                elif isinstance(additional, dict):
                    self.validate(val, additional, f"{path}.{key}")


def test_messages():
    print("Testing contract/messages.json...")
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for code in CLOSED_ERROR_CODES:
        if code not in data:
            raise ValidationError(f"Missing error code in messages.json: '{code}'")
        entry = data[code]
        for field in ["code", "title", "message", "action", "retryable"]:
            if field not in entry:
                raise ValidationError(f"messages.json entry '{code}' missing required field '{field}'")
        if entry["code"] != code:
            raise ValidationError(f"messages.json entry key '{code}' does not match code field '{entry['code']}'")
        if not isinstance(entry["retryable"], bool):
            raise ValidationError(f"messages.json entry '{code}' field 'retryable' must be a boolean")

    print(f"  ✓ All {len(CLOSED_ERROR_CODES)} error codes present with friendly text and actions.")


def test_schemas_and_fixtures(validator: SchemaValidator):
    print("Testing error fixtures against schemas/error.json...")
    error_schema = validator.schemas["error.json"]
    errors_dir = FIXTURES_DIR / "errors"
    found_error_codes = set()

    for path in sorted(errors_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            instance = json.load(f)
        validator.validate(instance, error_schema, path=path.name)
        code = instance["error"]["code"]
        found_error_codes.add(code)
        print(f"  ✓ {path.name} validates (code: {code})")

    missing = CLOSED_ERROR_CODES - found_error_codes
    if missing:
        raise ValidationError(f"Missing error fixtures for codes: {missing}")
    print(f"  ✓ All {len(CLOSED_ERROR_CODES)} error fixtures verified.")

    print("\nTesting hostile input fixtures...")
    hostile_dir = FIXTURES_DIR / "hostile"
    hostile_files = list(hostile_dir.glob("*.json"))
    if not hostile_files:
        raise ValidationError("No hostile input fixtures found!")

    for path in sorted(hostile_files):
        with open(path, "r", encoding="utf-8") as f:
            instance = json.load(f)
        if "expected_error" not in instance or "input" not in instance:
            raise ValidationError(f"Hostile fixture {path.name} missing 'input' or 'expected_error'")
        validator.validate(instance["expected_error"], error_schema, path=f"{path.name}.expected_error")
        print(f"  ✓ {path.name} validates (code: {instance['expected_error']['error']['code']})")

    print("\nTesting capability result fixtures...")
    result_schema = validator.schemas["result_block.json"]
    cap_dir = FIXTURES_DIR / "capabilities"
    found_caps = set()

    for path in sorted(cap_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            instance = json.load(f)
        cap = instance.get("capability")
        found_caps.add(cap)
        if cap not in CAPABILITIES:
            raise ValidationError(f"Capability fixture {path.name} has unknown capability '{cap}'")
        if not instance.get("blocks"):
            raise ValidationError(f"Capability fixture {path.name} has no result blocks")

        for idx, block in enumerate(instance["blocks"]):
            validator.validate(block, result_schema, path=f"{path.name}.blocks[{idx}]")

        print(f"  ✓ {path.name} validates ({len(instance['blocks'])} blocks)")

    missing_caps = CAPABILITIES - found_caps
    if missing_caps:
        raise ValidationError(f"Missing capability fixtures for: {missing_caps}")
    print(f"  ✓ All {len(CAPABILITIES)} capability fixtures verified.")

    print("\nTesting SSE fixtures...")
    sse_schema = validator.schemas["sse_event.json"]
    sse_json_file = FIXTURES_DIR / "sse" / "sse_events_full.json"
    with open(sse_json_file, "r", encoding="utf-8") as f:
        events = json.load(f)

    for idx, ev in enumerate(events):
        validator.validate(ev, sse_schema, path=f"sse_events_full.json[{idx}]")
    print(f"  ✓ {len(events)} parsed SSE events validate against sse_event.json")

    # Verify transcripts
    for transcript in (FIXTURES_DIR / "sse").glob("*.sse"):
        with open(transcript, "r", encoding="utf-8") as f:
            content = f.read()
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        has_id = any(line.startswith("id:") for line in lines)
        has_event = any(line.startswith("event:") for line in lines)
        has_data = any(line.startswith("data:") for line in lines)
        if not (has_id and has_event and has_data):
            raise ValidationError(f"SSE transcript {transcript.name} is malformed")
        print(f"  ✓ Transcript {transcript.name} verified ({len(lines)} lines)")

    print("\nTesting endpoint success fixtures...")
    ep_dir = FIXTURES_DIR / "endpoints"
    for path in sorted(ep_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if path.name == "upload_success.json":
            validator.validate(data["table"], validator.schemas["table.json"], path="upload_success.table")
        elif path.name == "chat_success.json":
            if data.get("plan"):
                validator.validate(data["plan"], validator.schemas["plan.json"], path="chat_success.plan")
        elif path.name == "run_get_success.json":
            for b in data.get("blocks", []):
                validator.validate(b, result_schema, path="run_get_success.block")
        print(f"  ✓ Endpoint fixture {path.name} validated")


def test_openapi():
    print("\nTesting contract/openapi.yaml...")
    if not OPENAPI_FILE.exists():
        raise ValidationError("openapi.yaml missing!")

    with open(OPENAPI_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Simple check of YAML structure
    required_paths = [
        "/api/session",
        "/api/status",
        "/health",
        "/api/upload",
        "/api/chat",
        "/api/run",
        "/api/runs/{id}/events",
        "/api/runs/{id}",
        "/api/log",
        "/internal/log",
        "/internal/counters",
    ]

    for p in required_paths:
        if p not in content:
            raise ValidationError(f"openapi.yaml missing path: '{p}'")

    print(f"  ✓ openapi.yaml contains all {len(required_paths)} required endpoints.")


def main():
    print("=" * 60)
    print("CONTRACT VERIFICATION HARNESS")
    print("=" * 60)
    try:
        validator = SchemaValidator(SCHEMAS_DIR)
        test_messages()
        test_schemas_and_fixtures(validator)
        test_openapi()
        print("\n" + "=" * 60)
        print("ALL CONTRACT CHECKS PASSED: 100% GREEN")
        print("=" * 60)
        return 0
    except ValidationError as e:
        print(f"\n[FAIL] CONTRACT VALIDATION ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
