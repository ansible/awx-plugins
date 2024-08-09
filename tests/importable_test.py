from importlib.metadata import entry_points as _discover_entry_points


def test_entry_points_exposed():
    entry_points = _discover_entry_points(group='awx.credential_plugins')
    assert 'x' in entry_points
