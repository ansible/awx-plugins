"""Smoke tests related to loading entry points."""

from importlib.metadata import entry_points as _discover_entry_points
from subprocess import check_call as _invoke_command
from sys import executable as _current_runtime

import pytest


@pytest.mark.parametrize(
    'entry_points_group',
    (
        'awx_plugins.credentials',
    ),
)
def test_entry_points_exposed(entry_points_group: str) -> None:
    """Verify the plugin entry point is discoverable.

    This check relies on the plugin-declaring distribution package to be
    pre-installed.
    """
    entry_points = _discover_entry_points(group=entry_points_group)
    expected_entry_points = {
        'aim': 'aim_plugin',
        'conjur': 'conjur_plugin',
        'hashivault_kv': 'hashivault_kv_plugin',
        'hashivault_ssh': 'hashivault_ssh_plugin',
        'azure_kv': 'azure_keyvault_plugin',
        'centrify_vault_kv': 'centrify_plugin',
        'thycotic_dsv': 'dsv_plugin',
        'thycotic_tss': 'tss_plugin',
        'aws_secretsmanager_credential': 'aws_secretmanager_plugin',
    }
    for x in expected_entry_points.keys():
        assert x in entry_points.names

    for k, v in expected_entry_points.items():
        callable_ref_spec = entry_points[k].value
        import_ref, callable_sep, callable_ref = callable_ref_spec.partition(':')
        assert callable_sep
        assert v == str(callable_ref)

        test_is_importable_callable_cmd = (
            _current_runtime,
            '-c',
            f'from sys import exit; '
            f'from {import_ref} import {callable_ref}; '
            f'exit(not type({callable_ref}).__name__ == "CredentialPlugin")',
        )
        _invoke_command(test_is_importable_callable_cmd)
