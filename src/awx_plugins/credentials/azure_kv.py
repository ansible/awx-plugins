"""Microsoft Azure Key Vault Lookup Plugin.

This module defines a credential lookup plugin to authenticate and retrieve
secrets from an Azure Key Vault. If the Client ID, Tenant ID, and Client
Secret are provided it will create a credential with those. If one is missing,
it will attempt to use the Managed Identity of an Azure VM to create a
credential.

Functions:

- :func:`azure_keyvault_backend`: Creates a credential either with the fields
  provided or via the VM environment, and retrieves the secret from the Key
  Vault.
- ``azure_keyvault_plugin``: Defines the credential plugin interface.
"""

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

from azure.core import exceptions as _az_exc
from azure.core.credentials import TokenCredential
from azure.identity import (
    ClientSecretCredential,
    CredentialUnavailableError,
    ManagedIdentityCredential,
)
from azure.keyvault.secrets import SecretClient

# NOTE: `msrestazure` is deprecated and does not provide usable typing.
# NOTE: This suppression should be replaced by in-tree type stubs.
# NOTE: Alternatively, the dependency can be replaced.
from msrestazure import azure_cloud  # type: ignore[import-untyped]

from . import _types
from .plugin import CredentialPlugin


# https://github.com/Azure/msrestazure-for-python/blob/master/msrestazure/azure_cloud.py
clouds = [
    vars(azure_cloud)[n]
    for n in dir(azure_cloud)
    if n.startswith('AZURE_') and n.endswith('_CLOUD')
]
default_cloud = vars(azure_cloud)['AZURE_PUBLIC_CLOUD']


azure_keyvault_inputs: _types.PluginInputs = {
    'fields': [
        {
            'id': 'url',
            'label': _('Vault URL (DNS Name)'),
            'type': 'string',
            'format': 'url',
        },
        {
            'id': 'client',
            'label': _('Client ID'),
            'type': 'string',
        },
        {
            'id': 'secret',
            'label': _('Client Secret'),
            'type': 'string',
            'secret': True,
        },
        {
            'id': 'tenant',
            'label': _('Tenant ID'),
            'type': 'string',
        },
        {
            'id': 'cloud_name',
            'label': _('Cloud Environment'),
            'help_text': _('Specify which azure cloud environment to use.'),
            'choices': list({default_cloud.name} | {c.name for c in clouds}),
            'default': default_cloud.name,
        },
    ],
    'metadata': [
        {
            'id': 'secret_field',
            'label': _('Secret Name'),
            'type': 'string',
            'help_text': _('The name of the secret to look up.'),
        },
        {
            'id': 'secret_version',
            'label': _('Secret Version'),
            'type': 'string',
            'help_text': _(
                'Used to specify a specific secret version (if left empty, '
                'the latest version will be used).',
            ),
        },
    ],
    'required': [
        'url',
        'secret_field',
    ],
}


def _initialize_credential(
    tenant: str = '',
    client: str = '',
    secret: str = '',
) -> TokenCredential:
    explicit_credentials_provided = all((tenant, client, secret))

    if explicit_credentials_provided:
        return ClientSecretCredential(
            tenant_id=tenant,
            client_id=client,
            client_secret=secret,
        )

    return ManagedIdentityCredential()


# WPS211 "too many args" is controlled externally
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def azure_keyvault_backend(  # noqa: WPS211
    *,
    url: str,
    client: str = '',
    secret: str = '',
    tenant: str = '',
    secret_field: str,
    secret_version: str = '',
) -> str | None:
    """Get a credential and retrieve a secret from an Azure Key Vault.

    An empty string for an optional parameter counts as not provided.

    :param url: An Azure Key Vault URI.
    :param client: The Client ID  (optional).
    :param secret: The Client Secret  (optional).
    :param tenant: The Tenant ID  (optional).
    :param secret_field: The name of the secret to retrieve from the
        vault.
    :param secret_version: The version of the secret to retrieve
        (optional).
    :returns: The secret from the Key Vault.
    :raises RuntimeError: If the software is not being run on an Azure
        VM.
    """
    chosen_credential = _initialize_credential(tenant, client, secret)
    keyvault = SecretClient(credential=chosen_credential, vault_url=url)
    try:
        keyvault_secret = keyvault.get_secret(
            name=secret_field,
            version=secret_version,
        )
    except CredentialUnavailableError as secret_lookup_err:
        raise RuntimeError(
            'You are not operating on an Azure VM, so the Managed Identity '
            'feature is unavailable. Please provide the full Client ID, '
            'Client Secret, and Tenant ID or run the software on an Azure VM.',
        ) from secret_lookup_err
    except _az_exc.ServiceRequestError as request_err:
        raise RuntimeError(
            f'Failed to connect to Azure Key Vault: {request_err}',
        ) from request_err
    except _az_exc.AzureError as catchall_azure_error:
        raise RuntimeError(
            'Error retrieving secret from Azure Key Vault: '
            f'{catchall_azure_error}',
        ) from catchall_azure_error
    return keyvault_secret.value


azure_keyvault_plugin = CredentialPlugin(
    'Microsoft Azure Key Vault',
    inputs=azure_keyvault_inputs,
    backend=azure_keyvault_backend,
)
