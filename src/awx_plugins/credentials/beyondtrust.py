# mypy: disable-error-code="no-untyped-call, no-untyped-def"

"""BeyondTrust Password Safe / Secrets Safe credential lookup plugin."""

from __future__ import annotations

import threading
import time
from urllib.parse import urljoin

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

import requests

from . import _types
from .plugin import CertFiles, CredentialPlugin, raise_for_status


beyondtrust_inputs: _types.PluginInputs = {
    'fields': [
        {
            'id': 'url',
            'label': _('BeyondTrust API Base URL'),
            'type': 'string',
            'format': 'url',
            'help_text': _(
                'Base URL for the BeyondTrust public API, for example '
                'https://beyondtrust.example.com/BeyondTrust/api/public/v3',
            ),
        },
        {
            'id': 'client_id',
            'label': _('Client ID'),
            'type': 'string',
            'help_text': _(
                'OAuth2 client ID for an application user associated with an '
                'API Access Policy registration.',
            ),
        },
        {
            'id': 'client_secret',
            'label': _('Client Secret'),
            'type': 'string',
            'secret': True,
            'help_text': _('OAuth2 client secret for the application user.'),
        },
        {
            'id': 'verify',
            'label': _('Verify SSL Certificates'),
            'type': 'boolean',
            'default': True,
        },
        {
            'id': 'cacert',
            'label': _('Custom CA Certificate'),
            'type': 'string',
            'secret': True,
            'multiline': True,
            'help_text': _(
                'Optional PEM-encoded CA certificate used when verifying the '
                'BeyondTrust appliance TLS certificate.',
            ),
        },
    ],
    'metadata': [
        {
            'id': 'secret_path',
            'label': _('Secret Path'),
            'type': 'string',
            'help_text': _(
                'Optional Secrets Safe folder path filter, for example '
                '/Team/Folder. Leave blank to search by title only.',
            ),
        },
        {
            'id': 'secret_title',
            'label': _('Secret Title'),
            'type': 'string',
            'help_text': _(
                'Full title of the secret in Secrets Safe. At least one of '
                'Secret Path or Secret Title is required.',
            ),
        },
        {
            'id': 'secret_field',
            'label': _('Secret Field'),
            'type': 'string',
            'default': 'password',
            'help_text': _(
                'Field to extract from the decrypted secret. Common values '
                'include password, Password, username, and private_key.',
            ),
        },
    ],
    'required': ['url', 'client_id', 'client_secret', 'secret_field'],
}


_TOKEN_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
_TOKEN_LOCK = threading.Lock()
_TOKEN_SKEW_SECONDS = 30


def _normalize_base_url(url: str) -> str:
    return url if url.endswith('/') else f'{url}/'


def _ssl_verify(verify: bool, cacert: str | None):
    if cacert:
        return CertFiles(cacert)
    return _NullCertContext(verify)


class _NullCertContext:
    def __init__(self, verify):
        self.verify = verify

    def __enter__(self):
        return self.verify

    def __exit__(self, *args):
        return None


def _request_token(
    url: str,
    client_id: str,
    client_secret: str,
    verify,
) -> tuple[str, float]:
    token_url = urljoin(_normalize_base_url(url), 'Auth/Connect/Token')
    response = requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        verify=verify,
        timeout=(5, 30),
    )
    raise_for_status(response)
    payload = response.json()
    try:
        access_token = payload['access_token']
    except KeyError as exc:
        raise RuntimeError(
            'BeyondTrust OAuth token response did not include access_token',
        ) from exc
    expires_in = int(payload.get('expires_in', 300))
    expires_at = time.monotonic() + max(expires_in - _TOKEN_SKEW_SECONDS, 1)
    return access_token, expires_at


def _get_access_token(
    url: str,
    client_id: str,
    client_secret: str,
    verify,
) -> str:
    cache_key = (url, client_id)
    now = time.monotonic()
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(cache_key)
        if cached and cached[1] > now:
            return cached[0]

    access_token, expires_at = _request_token(
        url,
        client_id,
        client_secret,
        verify,
    )
    with _TOKEN_LOCK:
        _TOKEN_CACHE[cache_key] = (access_token, expires_at)
    return access_token


def clear_token_cache() -> None:
    """Clear cached OAuth tokens. Intended for tests."""
    with _TOKEN_LOCK:
        _TOKEN_CACHE.clear()


def _field_aliases(secret_field: str) -> list[str]:
    aliases = {
        'password': ['password', 'Password', 'Content'],
        'private_key': [
            'private_key',
            'PrivateKey',
            'privateKey',
            'Password',
            'password',
            'FileContent',
            'fileContent',
        ],
        'username': ['username', 'Username', 'UserName'],
    }
    key = secret_field.lower()
    if key in aliases:
        return aliases[key]
    return [secret_field, secret_field.capitalize(), secret_field.lower()]


def _extract_secret_value(secret: dict, secret_field: str):
    for candidate in _field_aliases(secret_field):
        if candidate in secret and secret[candidate] not in (None, ''):
            return secret[candidate]

    available = ', '.join(sorted(str(key) for key in secret))
    raise KeyError(
        f'Field {secret_field!r} not found in BeyondTrust secret; '
        f'available fields: {available}',
    )


def _build_secret_query_params(secret_path: str, secret_title: str) -> dict:
    params = {'decrypt': 'true', 'limit': 100}
    if secret_path:
        params['Path'] = secret_path
    if secret_title:
        params['Title'] = secret_title
    return params


def _unwrap_secrets_payload(secrets) -> list:
    if isinstance(secrets, list):
        return secrets
    if isinstance(secrets, dict):
        unwrapped = (
            secrets.get('data')
            or secrets.get('Secrets')
            or secrets.get('secrets')
            or []
        )
        if isinstance(unwrapped, list):
            return unwrapped
    raise RuntimeError(
        'Unexpected BeyondTrust secrets response; expected a list of secrets',
    )


def _select_matching_secret(secrets: list, secret_title: str) -> dict:
    if not secrets:
        raise RuntimeError(
            'No BeyondTrust Secrets Safe secret matched the provided path/title',
        )

    matches = secrets
    if len(matches) > 1 and secret_title:
        exact = [
            item
            for item in matches
            if str(item.get('Title') or item.get('title') or '')
            == secret_title
        ]
        if exact:
            matches = exact

    if len(matches) > 1:
        raise RuntimeError(
            'Multiple BeyondTrust secrets matched; refine Secret Path and/or Secret Title',
        )
    return matches[0]


def _fetch_secrets(url: str, client_id: str, client_secret: str, verify, cacert, params):
    secrets_url = urljoin(_normalize_base_url(url), 'secrets-safe/secrets')
    with _ssl_verify(verify, cacert) as ssl_verify:
        access_token = _get_access_token(
            url,
            client_id,
            client_secret,
            ssl_verify,
        )
        response = requests.get(
            secrets_url,
            params=params,
            headers={'Authorization': f'Bearer {access_token}'},
            verify=ssl_verify,
            timeout=(5, 30),
        )
        raise_for_status(response)
        return response.json()


def beyondtrust_backend(**kwargs):
    url = kwargs['url']
    client_id = kwargs['client_id']
    client_secret = kwargs['client_secret']
    verify = kwargs.get('verify', True)
    cacert = kwargs.get('cacert') or None
    secret_path = (kwargs.get('secret_path') or '').strip()
    secret_title = (kwargs.get('secret_title') or '').strip()
    secret_field = kwargs.get('secret_field') or 'password'

    if not secret_path and not secret_title:
        raise RuntimeError(
            'At least one of Secret Path or Secret Title must be provided',
        )

    params = _build_secret_query_params(secret_path, secret_title)
    payload = _fetch_secrets(
        url,
        client_id,
        client_secret,
        verify,
        cacert,
        params,
    )
    secrets = _unwrap_secrets_payload(payload)
    secret = _select_matching_secret(secrets, secret_title)
    return _extract_secret_value(secret, secret_field)


beyondtrust_plugin = CredentialPlugin(
    'BeyondTrust Password Safe Lookup',
    inputs=beyondtrust_inputs,
    backend=beyondtrust_backend,
)
