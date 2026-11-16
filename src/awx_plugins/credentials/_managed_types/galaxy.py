"""Ansible Galaxy and Automation Hub service account credential type."""

from awx_plugins.interfaces._temporary_private_api import (  # noqa: WPS436
    ManagedCredentialType,
)
from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

galaxy_service_account = ManagedCredentialType(
    namespace='galaxy_service_account',
    kind='galaxy',
    name=_('Ansible Galaxy/Automation Hub Service Account'),
    managed=True,
    inputs={
        'fields': [
            {
                'id': 'url',
                'label': _('Galaxy Server URL'),
                'type': 'string',
                'help_text': _(
                    'The URL of the Galaxy instance to connect to.',
                ),
            },
            {
                'id': 'auth_url',
                'label': _('Auth Server URL'),
                'type': 'string',
                'help_text': _(
                    'The URL of a Keycloak server token_endpoint for '
                    'service account authentication.',
                ),
            },
            {
                'id': 'client_id',
                'label': _('Client ID'),
                'type': 'string',
                'help_text': _(
                    'Client ID for Keycloak service account authentication. '
                    'Requires ansible-core 2.19+.',
                ),
            },
            {
                'id': 'client_secret',
                'label': _('Client Secret'),
                'type': 'string',
                'secret': True,
                'help_text': _(
                    'Client Secret for Keycloak service account authentication. '
                    'Requires ansible-core 2.19+.',
                ),
            },
        ],
        'required': ['url', 'client_id', 'client_secret'],
    },
)
