"""Smoke tests related to loading entry points."""

from importlib.metadata import entry_points as _discover_entry_points
from subprocess import check_call as _invoke_command
from sys import executable as _current_runtime

import pytest


@pytest.mark.parametrize(
    'entry_points_group',
    (
        'awx.credential_plugins',
        'awx_plugins.credentials',
    ),
)
def test_entry_points_exposed(entry_points_group: str) -> None:
    """Verify the plugin entry point is discoverable.

    This check relies on the plugin-declaring distribution package to be
    pre-installed.
    """
    entry_points = _discover_entry_points(group=entry_points_group)
    assert 'x' in entry_points.names

    assert entry_points['x'].value == 'awx_plugins.credentials.x.api:XPlugin'

    test_is_importable_callable_cmd = (
        _current_runtime,
        '-c',
        'from importlib.metadata import entry_points; '
        'from sys import exit; '
        f'exit(not callable(entry_points(group="{entry_points_group}")["x"].load()))',
    )
    _invoke_command(test_is_importable_callable_cmd)
