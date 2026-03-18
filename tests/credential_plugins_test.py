import pytest
from pytest_mock import MockerFixture

import requests

from awx_plugins.credentials import aim


def test_imported_azure_cloud_sdk_vars() -> None:
    from awx_plugins.credentials import azure_kv

    assert len(azure_kv.clouds) > 0
    assert all([hasattr(c, 'name') for c in azure_kv.clouds])
    assert all([hasattr(c, 'suffixes') for c in azure_kv.clouds])
    assert all([hasattr(c.suffixes, 'keyvault_dns') for c in azure_kv.clouds])


class TestDelineaImports:
    """These module have a try-except for ImportError which will allow using
    the older library but we do not want the awx_devel image to have the older
    library, so these tests are designed to fail if these wind up using the
    fallback import."""

    def test_dsv_import(self) -> None:
        from awx_plugins.credentials.dsv import SecretsVault  # noqa: F401

        # assert this module as opposed to older thycotic.secrets.vault
        assert SecretsVault.__module__ == 'delinea.secrets.vault'

    def test_tss_import(self) -> None:
        from awx_plugins.credentials.tss import (  # noqa: F401
            DomainPasswordGrantAuthorizer,
            PasswordGrantAuthorizer,
            SecretServer,
            ServerSecret,
        )

        for cls in (
            DomainPasswordGrantAuthorizer,
            PasswordGrantAuthorizer,
            SecretServer,
            ServerSecret,
        ):
            # assert this module as opposed to older thycotic.secrets.server
            assert cls.__module__ == 'delinea.secrets.server'


@pytest.mark.parametrize(
    (
        'reason',
        'expected_url_in_exc',
        'expected_response_url_literal',
    ),
    (
        pytest.param(
            'foobar123',
            r'.*http://testurl\.com/AIMWebService/api/Accounts\?'
            r'AppId=\*\*\*\*&Query=\*\*\*\*&QueryFormat=test&'
            r'reason=\*\*\*\*.*',
            'http://testurl.com/AIMWebService/api/Accounts?'
            'AppId=****&Query=****&QueryFormat=test&reason=****',
            id='with-reason',
        ),
        pytest.param(
            '',
            r'.*http://testurl\.com/AIMWebService/api/Accounts\?'
            r'AppId=\*\*\*\*&Query=\*\*\*\*&QueryFormat=test.*',
            'http://testurl.com/AIMWebService/api/Accounts?'
            'AppId=****&Query=****&QueryFormat=test',
            id='no-reason',
        ),
    ),
)
def test_aim_sensitive_traceback_masked(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
    expected_url_in_exc: str,
    expected_response_url_literal: str,
) -> None:
    """Ensure that the sensitive information is not leaked in the traceback."""
    my_response = requests.Response()
    my_response.status_code = 404
    my_response.url = 'not_found'

    aim_request_mock = mocker.Mock(
        autospec=True,
        name='aim_request',
        return_value=my_response,
    )
    monkeypatch.setattr(aim.requests, 'get', aim_request_mock)

    with pytest.raises(
        requests.exceptions.HTTPError,
        match=expected_url_in_exc,
    ) as e:
        aim.aim_backend(  # type: ignore[no-untyped-call]
            url='http://testurl.com',
            app_id='foobar123',
            object_query='foobar123',
            object_query_format='test',
            reason=reason,
            verify=True,
        )

    assert e.value.response.url == expected_response_url_literal
    assert 'foobar123' not in str(e)
