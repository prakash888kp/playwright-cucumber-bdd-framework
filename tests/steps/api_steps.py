"""Generic data-driven API steps using context.api."""
import json
from pathlib import Path

import jsonschema
from pytest_bdd import parsers, step

from framework.helpers import data_manager

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "config" / "schemas"


@step(parsers.parse('I load API data for "{tc_id}"'))
def load_api_data(context, tc_id):
    context.data["api"] = data_manager.get_data("APIData", tc_id)
    row = context.data["api"]
    context.log.info(f"Loaded API data for {tc_id}: {row['Method']} {row['Endpoint']}")


@step("I send a GET request to the endpoint from test data")
def send_get_request(context):
    context.api.get(context.data["api"]["Endpoint"])


@step("I send a POST request with the payload from test data")
def send_post_request(context):
    payload = json.loads(context.data["api"]["Payload"] or "{}")
    context.api.post(context.data["api"]["Endpoint"], payload)


@step("the response status should match the expected status")
def response_status_should_match(context):
    expected = int(context.data["api"]["ExpectedStatus"])
    actual = context.api.status()
    assert actual == expected, f"Expected HTTP {expected}, got {actual}"
    context.log.info(f"Status {expected} verified")


@step(parsers.parse('the response field "{field_path}" should not be empty'))
def response_field_not_empty(context, field_path):
    value = context.api.body_path(field_path)
    assert value not in (None, ""), (
        f'Response field "{field_path}" is empty. '
        f"Body: {json.dumps(context.api.body(), default=str)[:500]}"
    )
    context.log.info(f'Field "{field_path}" = {json.dumps(value, default=str)}')


@step(parsers.parse('the response field "{field_path}" should equal "{expected}"'))
def response_field_should_equal(context, field_path, expected):
    value = context.api.body_path(field_path)
    assert str(value) == expected, f'Field "{field_path}": expected "{expected}", got "{value}"'


@step(parsers.parse('the response should match the JSON schema "{schema_file}"'))
def response_matches_schema(context, schema_file):
    schema = json.loads((SCHEMAS_DIR / schema_file).read_text(encoding="utf-8"))
    try:
        jsonschema.validate(context.api.body(), schema)
    except jsonschema.ValidationError as exc:
        raise AssertionError(f"Response violates schema {schema_file}: {exc.message}") from exc
    context.log.info(f"Response conforms to schema {schema_file}")
