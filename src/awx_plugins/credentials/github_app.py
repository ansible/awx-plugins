# # FIXME: the following violations must be addressed gradually and unignored
# # mypy: disable-error-code="no-untyped-call, no-untyped-def"

# from urllib.parse import quote, urlencode, urljoin

# from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
#     gettext_noop as _,
# )

# import requests as requests

# from .plugin import CertFiles, CredentialPlugin, raise_for_status

# from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
#     gettext_noop,
# )



# def github_app_backend(**kwargs):
#     github_url = kwargs.get("github_url")
#     app_id = kwargs.get("app_id")
#     installation_id = int(kwargs.get("install_id"))
#     private_key = kwargs.get("ssh_key_data")
#     jwt_expiry = int(kwargs.get("jwt_expiry", 600))

#     missing_parameters = []
#     if not github_url:
#         missing_parameters.append("GitHub URL")
#     if not installation_id:
#         missing_parameters.append("Installation ID")
#     if not app_id:
#         missing_parameters.append("Application ID")
#     if not private_key:
#         missing_parameters.append("Private Key")
#     if missing_parameters:
#         raise Exception.MissingParameterError(missing_parameters)
    
#     auth = Auth.AppAuth(app_id=app_id, private_key=private_key, jwt_expiry=jwt_expiry).get_installation_auth(
#         installation_id=installation_id

#     # In order to generate a token we have to make an initial call
#     # to GitHub even though we dont need to interact with GitHub.
#     Github(auth=auth)

#     return auth.token

# github_app_lookup_plugin = CredentialPlugin("GitHub App Authentication", inputs=github_app_inputs, backend=github_app_backend)