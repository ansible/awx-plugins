"""Test that numeric fields have appropriate types.

This test validates the field definitions in plugins.py to ensure that
fields with numeric semantics (timeout, port, count, etc.) are defined
with numeric types rather than string types, which would cause runtime
conversion errors.
"""

import pytest

from awx_plugins.credentials import plugins


def get_all_credential_types():
    """Get all ManagedCredentialType instances from the plugins module."""
    credential_types = []
    for attr_name in dir(plugins):
        attr = getattr(plugins, attr_name)
        if hasattr(attr, 'inputs') and hasattr(attr, 'namespace'):
            credential_types.append(attr)
    return credential_types


def get_all_fields():
    """Yield all fields across all credential types."""
    for cred_type in get_all_credential_types():
        if not cred_type.inputs or 'fields' not in cred_type.inputs:
            continue

        for field in cred_type.inputs['fields']:
            yield cred_type.namespace, field


# Keywords that indicate a field should be numeric (int or float)
NUMERIC_FIELD_INDICATORS = [
    'timeout',
    'port',
    'retry',
    'retries',
    'limit',
    'max',
    'min',
    'count',
    'interval',
    'duration',
]


def is_numeric_field(field_id: str, help_text: str | None = None) -> bool:
    """Determine if a field should be numeric based on its id or help text."""
    field_id_lower = field_id.lower()

    # Check field ID for numeric indicators
    for indicator in NUMERIC_FIELD_INDICATORS:
        if indicator in field_id_lower:
            return True

    # Check help text for timeout/duration mentions
    if help_text:
        help_lower = help_text.lower()
        if any(
            word in help_lower
            for word in ['timeout', 'seconds', 'milliseconds']
        ):
            # But exclude if it's clearly about a string/path
            if not any(
                word in help_lower
                for word in ['url', 'path', 'string', 'name']
            ):
                return True

    return False


@pytest.mark.parametrize(
    'namespace,field',
    [
        (ns, f)
        for ns, f in get_all_fields()
        if is_numeric_field(f['id'], f.get('help_text'))
    ],
    ids=lambda params: (
        f'{params[0]}.{params[1]["id"]}'
        if isinstance(params, tuple)
        and len(params) == 2
        and isinstance(params[1], dict)
        else None
    ),
)
def test_numeric_fields_have_numeric_types(
    namespace: str,
    field: dict,
) -> None:
    """Test that fields with numeric semantics have numeric types.

    This test identifies fields that should be numeric based on their name
    (e.g., 'timeout', 'port', 'retry') or help text, and ensures they're
    defined as 'int' rather than 'string'.

    This catches bugs where timeout/port/count fields are incorrectly
    defined as strings, which causes runtime conversion errors.
    """
    field_id = field['id']
    field_type = field['type']

    assert field_type in ('int', 'float'), (
        f"Field '{namespace}.{field_id}' appears to be numeric "
        f"(timeout/port/count/etc.) but is defined as type '{field_type}'. "
        f"It should be 'int' or 'float'."
    )

    # If there's a default value, verify it's actually numeric
    if 'default' in field:
        default = field['default']
        assert isinstance(default, (int, float)), (
            f"Field '{namespace}.{field_id}' has type '{field_type}' "
            f'but default value {default!r} is type {type(default).__name__}'
        )
