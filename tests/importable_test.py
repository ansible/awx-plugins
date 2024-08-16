"""Smoke tests related to loading entry points."""

from dataclasses import dataclass
from importlib.metadata import entry_points as _discover_entry_points

import pytest

from awx_plugins.inventory.plugins import PluginFileInjector


@dataclass(frozen=True)
class EntryPointParam:
    """Data structure representing a single exposed plugin."""

    group: str
    name: str
    spec: str

    def __str__(self):
        """Render an entry-point parameter as a string.

        To be used as a part of parametrized test ID.
        """
        return f'{self.name}={self.spec}@{self.group}'


credential_plugins = (
    EntryPointParam(
        'awx_plugins.credentials',
        'aim',
        'awx_plugins.credentials.aim:aim_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'conjur',
        'awx_plugins.credentials.conjur:conjur_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'hashivault_kv',
        'awx_plugins.credentials.hashivault:hashivault_kv_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'hashivault_ssh',
        'awx_plugins.credentials.hashivault:hashivault_ssh_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'azure_kv',
        'awx_plugins.credentials.azure_kv:azure_keyvault_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'centrify_vault_kv',
        'awx_plugins.credentials.centrify_vault:centrify_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'thycotic_dsv',
        'awx_plugins.credentials.dsv:dsv_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'thycotic_tss',
        'awx_plugins.credentials.tss:tss_plugin',
    ),
    EntryPointParam(
        'awx_plugins.credentials',
        'aws_secretsmanager_credential',
        'awx_plugins.credentials.aws_secretsmanager:aws_secretmanager_plugin',
    ),
)


inventory_plugins = (
    EntryPointParam(
        'awx_plugins.inventory',
        'azure-rm',
        'awx_plugins.inventory.plugins:azure_rm',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'ec2',
        'awx_plugins.inventory.plugins:ec2',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'gce',
        'awx_plugins.inventory.plugins:gce',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'vmware',
        'awx_plugins.inventory.plugins:vmware',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'openstack',
        'awx_plugins.inventory.plugins:openstack',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'rhv',
        'awx_plugins.inventory.plugins:rhv',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'satellite6',
        'awx_plugins.inventory.plugins:satellite6',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'terraform',
        'awx_plugins.inventory.plugins:terraform',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'controller',
        'awx_plugins.inventory.plugins:controller',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'insights',
        'awx_plugins.inventory.plugins:insights',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'openshift_virtualization',
        'awx_plugins.inventory.plugins:openshift_virtualization',
    ),
    EntryPointParam(
        'awx_plugins.inventory',
        'constructed',
        'awx_plugins.inventory.plugins:constructed',
    ),
)


with_credential_plugins = pytest.mark.parametrize(
    'entry_point',
    credential_plugins,
    ids=str,
)


with_inventory_plugins = pytest.mark.parametrize(
    'entry_point',
    inventory_plugins,
    ids=str,
)


with_all_plugins = pytest.mark.parametrize(
    'entry_point',
    credential_plugins + inventory_plugins,
    ids=str,
)


@with_all_plugins
def test_entry_points_exposed(entry_point: str) -> None:
    """Verify the plugin entry points are discoverable.

    This check relies on the plugin-declaring distribution package to be
    pre-installed.
    """
    entry_points = _discover_entry_points(group=entry_point.group)

    assert entry_point.name in entry_points.names
    assert entry_points[entry_point.name].value == entry_point.spec


@with_credential_plugins
def test_entry_points_are_credential_plugin(entry_point: str) -> None:
    """Ensure all exposed credential plugins are of the same class."""
    entry_points = _discover_entry_points(group=entry_point.group)
    loaded_plugin_class = entry_points[entry_point.name].load()

    loaded_plugin_class_name = type(loaded_plugin_class).__name__
    assert loaded_plugin_class_name == 'CredentialPlugin'


@with_inventory_plugins
def test_entry_points_are_inventory_plugin(entry_point: str) -> None:
    """Ensure all exposed inventory plugins are of the same class."""
    entry_points = _discover_entry_points(group=entry_point.group)
    loaded_plugin_class = entry_points[entry_point.name].load()

    assert issubclass(loaded_plugin_class, PluginFileInjector)
