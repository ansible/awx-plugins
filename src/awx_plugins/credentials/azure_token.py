"""Microsoft Azure OIDC token Lookup Plugin.

This module defines a credential lookup plugin to authenticate and retrieve
an OIDC token from Azure. If the Client ID, Tenant ID, and Client
Secret are provided it will create a credential with those. If one is missing,
it will attempt to use the Managed Identity of an Azure VM to create a
credential.

Functions:

- :func:`azure_oidc_backend`: Creates a credential either with the fields
  provided or via the VM environment, and retrieves the token from Azure.
- ``azure_oidc_plugin``: Defines the credential plugin interface.
"""

import inspect

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

# NOTE: `msrestazure` is deprecated and does not provide usable typing.
# NOTE: This suppression should be replaced by in-tree type stubs.
# NOTE: Alternatively, the dependency can be replaced.
from msrestazure import azure_cloud  # type: ignore[import-untyped]

from . import _types
from .plugin import CredentialPlugin


# https://github.com/Azure/msrestazure-for-python/blob/master/msrestazure/azure_cloud.py
clouds: list[azure_cloud.Cloud] = [
    cloud[1]
    for cloud in inspect.getmembers(azure_cloud)
    if isinstance(cloud[1], azure_cloud.Cloud)
]
default_cloud: azure_cloud.Cloud = azure_cloud.AZURE_PUBLIC_CLOUD


azure_oidc_inputs: _types.PluginInputs = {
    'fields': [
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
            'choices': list({default_cloud.name} | {cloud.name for cloud in clouds}),
            'default': default_cloud.name,
        },
    ],
    'metadata': [
        {
            'id': 'url',
            'label': _('Scope Parameter (DNS Name)'),
            'type': 'string',
            'format': 'url',
            'default': 'https://ossrdbms-aad.database.windows.net/.default',
            'help_text': _(
                'The requested scope parameter in the call to get_token.',
            ),
        },
    ],
    'required': [
        'url',
        'cloud_name',
    ],
}


def _initialize_credential(
    cloud_environment: azure_cloud.Cloud,
    tenant: str = '',
    client: str = '',
    secret: str = '',
) -> TokenCredential:
    explicit_credentials_provided = all((tenant, client, secret))

    if not explicit_credentials_provided and (tenant or secret):
        raise RuntimeError(
            'Client ID, Client Secret, and Tenant ID must be provided '
            'together for Service Principal authentication, '
            'or leave Tenant and Secret empty to use Managed Identity.',
        )
    if explicit_credentials_provided:
        adfs_authority_url = cloud_environment.endpoints.active_directory
        return ClientSecretCredential(
            tenant_id=tenant,
            client_id=client,
            client_secret=secret,
            authority=adfs_authority_url,
        )

    return ManagedIdentityCredential(
        client_id=client or None,
    )


def match_cloud(
    cloud_name: str,
) -> azure_cloud.Cloud:
    """Match a cloud_environment from cloud_name.

    :param cloud_name: The Name of the Azure Cloud to target.
    """
    matched_clouds: list[azure_cloud.Cloud] = [
        cloud for cloud in clouds if cloud.name == cloud_name
    ]
    if len(matched_clouds) == 1:
        cloud_environment = matched_clouds[0]
    elif len(matched_clouds) > 1:
        message = "Azure SDK failure: more than one cloud matched " \
                  f"for cloud_environment name '{cloud_name}'"
        raise RuntimeError(message)
    else:
        message = f"cloud_environment '{cloud_name}' could not be resolved."
        raise RuntimeError(message)
    return cloud_environment


# WPS211 "too many args" is controlled externally
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def azure_oidc_backend(  # noqa: WPS211
    *,
    url: str,
    cloud_name: str,
    client: str = '',
    secret: str = '',
    tenant: str = '',
    **kwargs: str,
) -> str | None:
    """Get a credential and retrieve OIDC token from Azure.

    An empty string for an optional parameter counts as not provided.

    :param url: Scope Parameter for OIDC token.
    :param cloud_name: The Name of the Azure Cloud to target.
    :param client: The Client ID  (optional).
    :param secret: The Client Secret  (optional).
    :param tenant: The Tenant ID  (optional).
    :returns: The token from OIDC.
    :raises RuntimeError: If the software is not being run on an Azure
        VM.
    """
    cloud_environment = match_cloud(cloud_name)
    chosen_credential = _initialize_credential(
        cloud_environment,
        tenant,
        client,
        secret,
    )
    try:
        token = chosen_credential.get_token(url).token
    except CredentialUnavailableError as oidc_lookup_err:
        raise RuntimeError(
            'You are not operating on an Azure VM, so the Managed Identity '
            'feature is unavailable. Please provide the full Client ID, '
            'Client Secret, and Tenant ID or run the software on an Azure VM.',
        ) from oidc_lookup_err
    except _az_exc.ClientAuthenticationError as request_err:
        raise RuntimeError(
            f'Failed to connect: {request_err}',
        ) from request_err
    except _az_exc.AzureError as catchall_azure_error:
        raise RuntimeError(
            f'Error retrieving token from Azure: {catchall_azure_error}',
        ) from catchall_azure_error
    return token


azure_oidc_plugin = CredentialPlugin(
    'Microsoft Azure OIDC Token',
    inputs=azure_oidc_inputs,
    backend=azure_oidc_backend,
)
