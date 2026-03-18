"""Tests Azure Key Vault credential plugin."""

import pytest
from pytest_mock import MockerFixture

from azure.identity import CredentialUnavailableError
from azure.keyvault.secrets import (
    KeyVaultSecret,
    SecretClient,
    SecretProperties,
)

from awx_plugins.credentials import azure_kv


class _FakeSecretClient(SecretClient):
    def get_secret(
        self: '_FakeSecretClient',
        name: str,
        version: str | None = None,
        **kwargs: str,
    ) -> KeyVaultSecret:
        props = SecretProperties()
        return KeyVaultSecret(properties=props, value='test-secret')


def test_azure_kv_invalid_env(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test running outside of Azure raises error.

    When credentials are incomplete (e.g., empty client ID), the code falls
    back to ManagedIdentityCredential. On a non-Azure VM, this raises
    CredentialUnavailableError. Using a fake vault URL in tests would cause
    a DNS error before the credential check, so we mock SecretClient to
    simulate the expected CredentialUnavailableError.
    """
    mock_client = mocker.Mock()
    mock_client.return_value.get_secret.side_effect = (
        CredentialUnavailableError(
            message='ManagedIdentityCredential authentication unavailable.',
        )
    )
    monkeypatch.setattr(azure_kv, 'SecretClient', mock_client)

    error_msg = (
        'You are not operating on an Azure VM, so the Managed Identity '
        'feature is unavailable. Please provide the full Client ID, '
        'Client Secret, and Tenant ID or run the software on an Azure VM.'
    )

    with pytest.raises(
        RuntimeError,
        match=error_msg,
    ):
        azure_kv.azure_keyvault_backend(
            url='https://test.vault.azure.net',
            client='',
            secret='client-secret',
            tenant='tenant-id',
            secret_field='secret',
            secret_version='',
        )


@pytest.mark.parametrize(
    ('client', 'secret', 'tenant'),
    (
        pytest.param('', '', '', id='managed-identity'),
        pytest.param(
            'client-id',
            'client-secret',
            'tenant-id',
            id='client-secret-credential',
        ),
    ),
)
def test_azure_kv_valid_auth(
    monkeypatch: pytest.MonkeyPatch,
    client: str,
    secret: str,
    tenant: str,
) -> None:
    """Test successful Azure authentication via Managed Identity and credentials."""
    monkeypatch.setattr(
        azure_kv,
        'SecretClient',
        _FakeSecretClient,
    )

    keyvault_secret = azure_kv.azure_keyvault_backend(
        url='https://test.vault.azure.net',
        client=client,
        secret=secret,
        tenant=tenant,
        secret_field='secret',
        secret_version='',
    )
    assert keyvault_secret == 'test-secret'
