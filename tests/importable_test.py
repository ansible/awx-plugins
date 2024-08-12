from subprocess import check_call as _invoke_command
from sys import executable as _current_runtime
from importlib.metadata import entry_points as _discover_entry_points


def test_entry_points_exposed():
    """Verify the plugin entry point is discoverable."""
    entry_points = _discover_entry_points(group='awx.credential_plugins')
    assert 'x' in entry_points.names

    callable_ref_spec = entry_points['x'].value
    import_ref, callable_sep, callable_ref = callable_ref_spec.partition(':')
    assert callable_sep

    test_is_importable_callable_cmd = (
        _current_runtime,
        '-c',
        f'from sys import exit; '
        f'from {import_ref} import {callable_ref}; '
        f'exit(not callable({callable_ref}))',
    )
    _invoke_command(test_is_importable_callable_cmd)
