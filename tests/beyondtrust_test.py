"""Tests BeyondTrust Secrets Safe credential plugin."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from awx_plugins.credentials import beyondtrust


@pytest.fixture(autouse=True)
def _clear_token_cache() -> None:
    beyondtrust.clear_token_cache()


def test_beyondtrust_backend_fetches_password(mocker: MockerFixture) -> None:
    """Auth + secret lookup should return the requested field."""
    post = mocker.patch('awx_plugins.credentials.beyondtrust.requests.post')
    get = mocker.patch('awx_plugins.credentials.beyondtrust.requests.get')

    post.return_value.status_code = 200
    post.return_value.json.return_value = {
        'access_token': 'token-1',
        'expires_in': 3600,
        'token_type': 'Bearer',
    }
    get.return_value.status_code = 200
    get.return_value.json.return_value = [
        {
            'Title': 'app-secret',
            'Password': 's3cret',
            'Username': 'svc-user',
        },
    ]

    result = beyondtrust.beyondtrust_backend(
        url='https://bt.example.com/BeyondTrust/api/public/v3',
        client_id='client',
        client_secret='secret',
        verify=True,
        secret_title='app-secret',
        secret_field='password',
    )

    assert result == 's3cret'
    assert post.call_args.kwargs['data']['grant_type'] == 'client_credentials'
    assert get.call_args.kwargs['params']['decrypt'] == 'true'
    assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer token-1'


def test_beyondtrust_reuses_cached_token(mocker: MockerFixture) -> None:
    """OAuth token should be reused for subsequent lookups in-process."""
    post = mocker.patch('awx_plugins.credentials.beyondtrust.requests.post')
    get = mocker.patch('awx_plugins.credentials.beyondtrust.requests.get')

    post.return_value.status_code = 200
    post.return_value.json.return_value = {
        'access_token': 'token-1',
        'expires_in': 3600,
        'token_type': 'Bearer',
    }
    get.return_value.status_code = 200
    get.return_value.json.return_value = [
        {'Title': 'app-secret', 'Password': 'one'},
    ]

    kwargs = {
        'url': 'https://bt.example.com/BeyondTrust/api/public/v3',
        'client_id': 'client',
        'client_secret': 'secret',
        'verify': True,
        'secret_title': 'app-secret',
        'secret_field': 'password',
    }
    beyondtrust.beyondtrust_backend(**kwargs)

    get.return_value.json.return_value = [
        {'Title': 'app-secret', 'Password': 'two'},
    ]
    result = beyondtrust.beyondtrust_backend(**kwargs)

    assert result == 'two'
    assert post.call_count == 1
    assert get.call_count == 2


def test_beyondtrust_requires_path_or_title() -> None:
    """Lookup metadata must include a path and/or title."""
    with pytest.raises(RuntimeError, match='Secret Path or Secret Title'):
        beyondtrust.beyondtrust_backend(
            url='https://bt.example.com/BeyondTrust/api/public/v3',
            client_id='client',
            client_secret='secret',
            secret_field='password',
        )


def test_beyondtrust_no_match(mocker: MockerFixture) -> None:
    """Empty secret lists should raise a clear error."""
    post = mocker.patch('awx_plugins.credentials.beyondtrust.requests.post')
    get = mocker.patch('awx_plugins.credentials.beyondtrust.requests.get')
    post.return_value.status_code = 200
    post.return_value.json.return_value = {
        'access_token': 'token-1',
        'expires_in': 3600,
    }
    get.return_value.status_code = 200
    get.return_value.json.return_value = []

    with pytest.raises(
        RuntimeError,
        match='No BeyondTrust Secrets Safe secret',
    ):
        beyondtrust.beyondtrust_backend(
            url='https://bt.example.com/BeyondTrust/api/public/v3',
            client_id='client',
            client_secret='secret',
            secret_title='missing',
            secret_field='password',
        )


def test_beyondtrust_private_key_alias(mocker: MockerFixture) -> None:
    """private_key should map onto common Secrets Safe field names."""
    post = mocker.patch('awx_plugins.credentials.beyondtrust.requests.post')
    get = mocker.patch('awx_plugins.credentials.beyondtrust.requests.get')
    post.return_value.status_code = 200
    post.return_value.json.return_value = {
        'access_token': 'token-1',
        'expires_in': 3600,
    }
    get.return_value.status_code = 200
    get.return_value.json.return_value = [
        {
            'Title': 'ssh-key',
            'Password': '-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----',
        },
    ]

    result = beyondtrust.beyondtrust_backend(
        url='https://bt.example.com/BeyondTrust/api/public/v3',
        client_id='client',
        client_secret='secret',
        secret_path='/keys',
        secret_title='ssh-key',
        secret_field='private_key',
    )

    assert 'BEGIN OPENSSH PRIVATE KEY' in result
