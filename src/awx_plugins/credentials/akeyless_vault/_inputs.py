"""Inputs shared by the Akeyless credential plugins."""

import typing as _t

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

from .. import _types


class EmptyKwargs(_t.TypedDict):
    """Schema for zero keyword arguments."""


OIDC_PLUGIN_DESCRIPTION = (
    'Uses OIDC/JWT authentication for enhanced security with short-lived '
    'tokens'
)


_gateway_url_field: _types.FieldDict = {
    'id': 'gateway_url',
    'label': _('Gateway URL'),
    'type': 'string',
    'help_text': _(
        'The URL of your Akeyless Gateway (e.g., https://api.akeyless.io, '
        'https://my.akeyless.gw/api/v2)',
    ),
    'default': 'https://api.akeyless.io',
}


# The OIDC credential types must name this field `url`: the controller reads
# the audience of the workload identity token it mints from the input with
# that exact name.
_url_field: _types.FieldDict = {
    'id': 'url',
    'label': _('Gateway URL'),
    'type': 'string',
    'help_text': _(
        'The URL of your Akeyless Gateway (e.g., https://api.akeyless.io, '
        'https://my.akeyless.gw/api/v2). This value is also sent as the '
        'audience of the workload identity token, so it must match the '
        'audience configured on the Akeyless JWT auth method.',
    ),
    'default': 'https://api.akeyless.io',
}


_access_id_field: _types.FieldDict = {
    'id': 'access_id',
    'label': _('Access ID'),
    'type': 'string',
    'help_text': _('Your Akeyless API Access ID'),
}


_oidc_access_id_field: _types.FieldDict = {
    'id': 'access_id',
    'label': _('Access ID'),
    'type': 'string',
    'help_text': _(
        'The Access ID of the Akeyless JWT auth method that trusts your '
        'automation platform as an OIDC issuer (e.g., p-1a2b3c4d5e6f).',
    ),
}


_access_key_field: _types.FieldDict = {
    'id': 'access_key',
    'label': _('Access Key'),
    'type': 'string',
    'help_text': _('Your Akeyless API Access Key'),
    'secret': True,
}


_ca_cert_field: _types.FieldDict = {
    'id': 'ca_cert',
    'label': _('CA Certificate'),
    'type': 'string',
    'multiline': True,
    'help_text': _(
        'CA certificate (PEM format) used to verify the gateway TLS '
        'certificate.',
    ),
}


_workload_identity_token_field: _types.FieldDict = {
    'id': 'workload_identity_token',
    'label': _('Workload Identity Token'),
    'type': 'string',
    'secret': True,
    'internal': True,
    'help_text': _(
        'JWT token for workload identity authentication. '
        'Automatically populated by the system.',
    ),
}


api_key_auth_fields: list[_types.FieldDict] = [
    _gateway_url_field,
    _access_id_field,
    _access_key_field,
    _ca_cert_field,
]

api_key_auth_required = ['gateway_url', 'access_id', 'access_key']


oidc_auth_fields: list[_types.FieldDict] = [
    _url_field,
    _oidc_access_id_field,
    _ca_cert_field,
    _workload_identity_token_field,
]

oidc_auth_required = ['url', 'access_id']
