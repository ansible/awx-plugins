"""HCP Terraform managed credential type."""

from awx_plugins.interfaces._temporary_private_api import (
    ManagedCredentialType,
)
from awx_plugins.interfaces._temporary_private_django_api import (
    gettext_noop,
)

from ..injectors import hcp_terraform as hcp_terraform_injector


# FIXME: ManagedCredentialType and gettext_noop return Any from
# _temporary_private_api interfaces. These nested Any structures cascade
# into making outer dicts/lists typed as Any as well, requiring suppressions
# throughout. Remove once those interfaces have proper type annotations.
hcp_terraform = ManagedCredentialType(  # type: ignore[misc]
    namespace='hcp_terraform',
    kind='cloud',
    name=gettext_noop('HCP Terraform'),  # type: ignore[misc]
    managed=True,
    custom_injectors=hcp_terraform_injector,
    inputs={
        'fields': [  # type: ignore[misc]
            {  # type: ignore[misc]
                'id': 'hostname',
                'label': gettext_noop('Hostname'),  # type: ignore[misc]
                'type': 'string',
                'help_text': gettext_noop(  # type: ignore[misc]
                    'The hostname of your HCP Terraform instance (e.g., app.terraform.io)',
                ),
                'default': 'app.terraform.io',
            },
            {  # type: ignore[misc]
                'id': 'token',
                'label': gettext_noop('API Token'),  # type: ignore[misc]
                'type': 'string',
                'secret': True,
                'help_text': gettext_noop(  # type: ignore[misc]
                    'HCP Terraform API Token',
                ),
            },
        ],
        'required': ['token'],
    },
)
