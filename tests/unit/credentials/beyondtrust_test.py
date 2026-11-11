"""Tests BeyondTrust Secrets Safe credential plugin."""

from __future__ import annotations

import pytest

import responses

from awx_plugins.credentials import beyondtrust


BASE_URL = 'https://bt.example.com/BeyondTrust/api/public/v3'


@pytest.fixture(autouse=True)
def _clear_token_cache() -> None:
    beyondtrust.clear_token_cache()


def _add_token_response() -> None:
    responses.add(
        responses.POST,
        f'{BASE_URL}/Auth/Connect/Token',
        json={
            'access_token': 'token-1',
            'expires_in': 3600,
            'token_type': 'Bearer',
        },
        status=200,
    )


@responses.activate
def test_beyondtrust_backend_fetches_password() -> None:
    """Auth + secret lookup should return the requested field."""
    _add_token_response()
    responses.add(
        responses.GET,
        f'{BASE_URL}/secrets-safe/secrets',
        json=[
            {
                'Title': 'app-secret',
                'Password': 's3cret',
                'Username': 'svc-user',
            },
        ],
        status=200,
    )

    result = beyondtrust.beyondtrust_backend(
        url=BASE_URL,
        client_id='client',
        client_secret='secret',
        verify=True,
        secret_title='app-secret',
        secret_field='password',
    )

    assert result == 's3cret'
    assert len(responses.calls) == 2
    assert 'grant_type=client_credentials' in str(
        responses.calls[0].request.body,
    )
    assert responses.calls[1].request.params['decrypt'] == 'true'
    assert (
        responses.calls[1].request.headers['Authorization'] == 'Bearer token-1'
    )


@responses.activate
def test_beyondtrust_reuses_cached_token() -> None:
    """OAuth token should be reused for subsequent lookups in-process."""
    _add_token_response()
    responses.add(
        responses.GET,
        f'{BASE_URL}/secrets-safe/secrets',
        json=[{'Title': 'app-secret', 'Password': 'one'}],
        status=200,
    )
    responses.add(
        responses.GET,
        f'{BASE_URL}/secrets-safe/secrets',
        json=[{'Title': 'app-secret', 'Password': 'two'}],
        status=200,
    )

    kwargs = {
        'url': BASE_URL,
        'client_id': 'client',
        'client_secret': 'secret',
        'verify': True,
        'secret_title': 'app-secret',
        'secret_field': 'password',
    }
    beyondtrust.beyondtrust_backend(**kwargs)
    result = beyondtrust.beyondtrust_backend(**kwargs)

    assert result == 'two'
    assert (
        len(
            [c for c in responses.calls if c.request.method == 'POST'],
        )
        == 1
    )
    assert (
        len(
            [c for c in responses.calls if c.request.method == 'GET'],
        )
        == 2
    )


def test_beyondtrust_requires_path_or_title() -> None:
    """Lookup metadata must include a path and/or title."""
    with pytest.raises(ValueError, match='Secret Path or Secret Title'):
        beyondtrust.beyondtrust_backend(
            url=BASE_URL,
            client_id='client',
            client_secret='secret',
            secret_field='password',
        )


@responses.activate
def test_beyondtrust_no_match() -> None:
    """Empty secret lists should raise a clear error."""
    _add_token_response()
    responses.add(
        responses.GET,
        f'{BASE_URL}/secrets-safe/secrets',
        json=[],
        status=200,
    )

    with pytest.raises(
        LookupError,
        match='No BeyondTrust Secrets Safe secret',
    ):
        beyondtrust.beyondtrust_backend(
            url=BASE_URL,
            client_id='client',
            client_secret='secret',
            secret_title='missing',
            secret_field='password',
        )


@responses.activate
def test_beyondtrust_private_key_alias() -> None:
    """private_key should map onto common Secrets Safe field names."""
    _add_token_response()
    responses.add(
        responses.GET,
        f'{BASE_URL}/secrets-safe/secrets',
        json=[
            {
                'Title': 'ssh-key',
                'Password': (
                    '-----BEGIN OPENSSH PRIVATE KEY-----\n'
                    'test\n'
                    '-----END OPENSSH PRIVATE KEY-----'
                ),
            },
        ],
        status=200,
    )

    result = beyondtrust.beyondtrust_backend(
        url=BASE_URL,
        client_id='client',
        client_secret='secret',
        secret_path='/keys',
        secret_title='ssh-key',
        secret_field='private_key',
    )

    assert 'BEGIN OPENSSH PRIVATE KEY' in result
