"""OAuth2 Client Credentials Token Credential Plugin.

This module defines a credential plugin that fetches a short-lived
bearer token using the OAuth 2.0 ``client_credentials`` grant.
Works with any compliant token endpoint including Microsoft Entra ID
(Azure AD), Keycloak, Okta, and others.

Primary use case: Azure DevOps project synchronisation after PAT/SSH
deprecation, using a Microsoft Entra Service Principal.

Functions:

- :func:`oauth2_client_credentials_backend`: Fetches an OAuth2 token.
- ``oauth2_client_credentials_plugin``: Defines the credential plugin
  interface.
"""

from typing import TypedDict, Unpack

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

import requests

from . import _types
from .plugin import CredentialPlugin


__all__ = ('oauth2_client_credentials_plugin',)  # noqa: WPS410

_REQUEST_TIMEOUT_SECONDS = 30


oauth2_client_credentials_inputs: _types.PluginInputs = {
    'fields': [
        {
            'id': 'token_url',
            'label': _('Token Endpoint URL'),
            'type': 'string',
            'help_text': _(
                'The full OAuth2 token endpoint URL. '
                'For Microsoft Entra ID: '
                'https://login.microsoftonline.com/'
                '<TENANT_ID>/oauth2/v2.0/token',
            ),
        },
        {
            'id': 'client_id',
            'label': _('Client ID'),
            'type': 'string',
            'help_text': _(
                'The OAuth2 client identifier '
                '(Application ID for Microsoft Entra).',
            ),
        },
        {
            'id': 'client_secret',
            'label': _('Client Secret'),
            'type': 'string',
            'secret': True,
            'help_text': _('The OAuth2 client secret.'),
        },
    ],
    'metadata': [
        {
            'id': 'scope',
            'label': _('Scope (optional)'),
            'type': 'string',
            'help_text': _(
                'The OAuth2 scope to request. '
                'For Azure DevOps: '
                '499b84ac-1321-427f-aa17-267ca6975798/.default',
            ),
        },
    ],
    'required': ['token_url', 'client_id', 'client_secret'],
}


class EmptyKwargs(TypedDict):
    """Schema for zero keyword arguments."""


def _extract_error_detail(resp: requests.Response) -> str:
    """Pull a human-readable error from a non-200 response.

    :param resp: The failed HTTP response.
    :returns: An error description string.
    """
    try:
        body: object = resp.json()
    except ValueError:
        return resp.text

    if not isinstance(body, dict):
        return resp.text
    return str(body.get('error_description', resp.text))


def _post_token_request(
    token_url: str,
    post_data: dict[str, str],
) -> requests.Response:
    """POST to the token endpoint, converting transport errors.

    :param token_url: The full OAuth2 token endpoint URL.
    :param post_data: The form data to send.
    :returns: The HTTP response.
    :raises ValueError: On any transport-level failure.
    """
    try:
        return requests.post(
            token_url,
            data=post_data,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as timeout_exc:
        raise ValueError(
            f'Timed out requesting token from {token_url!s}',
        ) from timeout_exc
    except requests.exceptions.ConnectionError as conn_exc:
        raise ValueError(
            f'Could not connect to token endpoint: {token_url!s}',
        ) from conn_exc
    except requests.exceptions.RequestException as req_exc:
        raise ValueError(
            f'Failed requesting token from endpoint: {token_url!s}',
        ) from req_exc


def _extract_access_token(resp: requests.Response) -> str:
    """Parse the access_token from a successful token response.

    :param resp: A 200 HTTP response from the token endpoint.
    :returns: The bearer access token string.
    :raises ValueError: If the response body is not valid JSON,
        is not a JSON object, or lacks ``access_token``.
    """
    try:
        body: object = resp.json()
    except ValueError as parse_exc:
        raise ValueError(
            'Token endpoint response did not contain an access_token field',
        ) from parse_exc

    if not isinstance(body, dict) or 'access_token' not in body:
        raise ValueError(
            'Token endpoint response did not contain an access_token field',
        )
    return str(body['access_token'])


def oauth2_client_credentials_backend(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str = '',
    **_discarded_kwargs: Unpack[EmptyKwargs],
) -> str:
    """Fetch an OAuth 2.0 access token via the client_credentials grant.

    Called each time a linked credential value needs to be resolved.
    The token is never cached; a fresh one is requested on every
    lookup.

    :param token_url: The full OAuth2 token endpoint URL.
    :param client_id: The OAuth2 client identifier.
    :param client_secret: The OAuth2 client secret.
    :param scope: Optional OAuth2 scope to request.
    :param _discarded_kwargs: Aren't expected to be passed.
    :returns: A bearer access token string.
    :raises ValueError: If the token request fails or the response
        is missing the ``access_token`` field.
    """
    post_data: dict[str, str] = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
    }
    if scope:
        post_data['scope'] = scope

    resp = _post_token_request(token_url, post_data)

    if resp.status_code != 200:  # noqa: WPS432
        raise ValueError(
            'Token request failed '
            f'(HTTP {resp.status_code}): '
            f'{_extract_error_detail(resp)!s}',
        )

    return _extract_access_token(resp)


oauth2_client_credentials_plugin = CredentialPlugin(
    'OAuth2 Client Credentials Token Lookup',
    inputs=oauth2_client_credentials_inputs,
    backend=oauth2_client_credentials_backend,
    plugin_description=(
        'Fetch a short-lived OAuth2 bearer token using the '
        'client_credentials grant. Works with Entra ID, '
        'Keycloak, Okta, and any compliant provider.'
    ),
)
