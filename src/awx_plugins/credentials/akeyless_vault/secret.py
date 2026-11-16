"""Credential plugins reading Akeyless static secrets."""

import json as _json
import typing as _t
from collections import abc as _abc

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

from akeyless import DescribeItem, GetSecretValue

from .. import _types
from ..plugin import CredentialPlugin
from . import _inputs, _session


__all__ = (  # noqa: WPS410
    'akeyless_backend',
    'akeyless_oidc_plugin',
    'akeyless_plugin',
)


_SUPPORTED_ITEM_TYPES = frozenset(('STATIC_SECRET',))

_STRUCTURED_SECRET_FORMATS = frozenset(('json', 'key-value'))

_PASSWORD_KEYS = frozenset(('username', 'password'))


_secret_metadata: list[_types.MetadataDict] = [
    {
        'id': 'secret_path',
        'label': _('Secret Path'),
        'type': 'string',
        'help_text': _(
            'The path to the secret in Akeyless (e.g., '
            '/myapp/database/password).',
        ),
    },
    {
        'id': 'secret_key',
        'label': _('Secret Key'),
        'type': 'string',
        'help_text': _(
            'Optional key within the secret to retrieve (for JSON or '
            'key-value secrets).',
        ),
    },
]


_akeyless_inputs: _types.PluginInputs = {
    'fields': _inputs.api_key_auth_fields,
    'metadata': _secret_metadata,
    'required': [*_inputs.api_key_auth_required, 'secret_path'],
}


_akeyless_oidc_inputs: _types.PluginInputs = {
    'fields': _inputs.oidc_auth_fields,
    'metadata': _secret_metadata,
    'required': [*_inputs.oidc_auth_required, 'secret_path'],
}


def _load_secret_json(secret_data: str) -> dict[str, str]:
    try:
        loaded_secret: object = _json.loads(secret_data)
    except _json.JSONDecodeError as exc:
        raise ValueError('Secret data not valid JSON') from exc
    if isinstance(loaded_secret, dict):
        return _t.cast('dict[str, str]', loaded_secret)
    raise ValueError('Secret data not a JSON object')


def _extract_password_secret(secret_data: str, secret_key: str | None) -> str:
    if not secret_key:
        return secret_data
    if secret_key not in _PASSWORD_KEYS:
        raise NotImplementedError(
            'Password secrets only support "username" or "password" keys.',
        )
    secret_dict = _load_secret_json(secret_data)
    try:
        return secret_dict[secret_key]
    except KeyError as exc:
        raise ValueError(
            f'Key "{secret_key}" not found in the password secret.',
        ) from exc


def _extract_text_secret(
    secret_data: str,
    secret_key: str | None,
    static_secret_sub_type: str,
) -> str:
    if static_secret_sub_type == 'password':
        return _extract_password_secret(secret_data, secret_key)
    if static_secret_sub_type == 'generic':
        return secret_data
    raise NotImplementedError(
        'Static secret sub type must be "password" or "generic".',
    )


def _extract_structured_secret(
    secret_data: str,
    secret_key: str | None,
    secret_path: str,
) -> str:
    if not secret_key:
        return secret_data
    secret_dict = _load_secret_json(secret_data)
    try:
        return secret_dict[secret_key]
    except KeyError as exc:
        raise ValueError(
            f'Key "{secret_key}" not found in secret at path: {secret_path}',
        ) from exc


def _extract_secret_value(
    secret_response: _abc.Mapping[str, str],
    secret_path: str,
    secret_key: str | None,
    static_secret_format: str,
    static_secret_sub_type: str,
) -> str:
    try:
        secret_data = secret_response[secret_path]
    except KeyError as exc:
        raise ValueError(
            f'No secret data returned for path: {secret_path}',
        ) from exc
    if static_secret_format == 'text':
        return _extract_text_secret(
            secret_data,
            secret_key,
            static_secret_sub_type,
        )
    if static_secret_format in _STRUCTURED_SECRET_FORMATS:
        return _extract_structured_secret(
            secret_data,
            secret_key,
            secret_path,
        )
    raise NotImplementedError(
        'Static secret format must be "text", "json", or "key-value".',
    )


@_session.inject_session
def akeyless_backend(
    *,
    secret_path: str,
    secret_key: str | None = None,
    **_discarded_kwargs: _t.Unpack[_inputs.EmptyKwargs],
) -> str:
    """Retrieve a static secret value from Akeyless.

    :param secret_path: The path to the secret in Akeyless.
    :param secret_key: The key to read from a structured secret.
    :param _discarded_kwargs: The authentication inputs, which
        :func:`~._session.inject_session` consumes.
    :returns: The secret value.
    :raises NotImplementedError: If the item is not a static secret.
    """
    api, token = _session.current_session()
    describe_item_response = api.describe_item(
        DescribeItem(name=secret_path, token=token),
    )
    item_type = describe_item_response.item_type
    if item_type not in _SUPPORTED_ITEM_TYPES:
        raise NotImplementedError(
            f'Secret "{secret_path}" is of type "{item_type}". '
            f'Supported types: {sorted(_SUPPORTED_ITEM_TYPES)}.',
        )

    secret_response = api.get_secret_value(
        GetSecretValue(names=[secret_path], token=token),
    )
    return _extract_secret_value(
        secret_response,
        secret_path,
        secret_key,
        describe_item_response.item_general_info.static_secret_info.format,
        describe_item_response.item_sub_type,
    )


akeyless_plugin = CredentialPlugin(
    'Akeyless',
    inputs=_akeyless_inputs,
    backend=akeyless_backend,
)


akeyless_oidc_plugin = CredentialPlugin(
    'Akeyless (OIDC)',
    inputs=_akeyless_oidc_inputs,
    backend=akeyless_backend,
    plugin_description=_inputs.OIDC_PLUGIN_DESCRIPTION,
)
