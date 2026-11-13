"""Authenticated Akeyless API sessions for the credential plugins."""

import contextlib as _ctx
import contextvars as _ctx_vars
import functools as _functools
import typing as _t
from collections import abc as _abc

from akeyless import ApiClient, Auth, Configuration, V2Api
from akeyless.rest import ApiException

from ..plugin import CertFiles


class AkeylessSession(_t.NamedTuple):
    """An Akeyless API client and the token it authenticated with."""

    api: V2Api
    token: str


class _AuthInputs(_t.TypedDict, total=False):
    """Credential type inputs used to authenticate to Akeyless."""

    access_id: str
    access_key: str
    ca_cert: str | None
    gateway_url: str
    url: str
    workload_identity_token: str


_SESSION: _ctx_vars.ContextVar[AkeylessSession] = _ctx_vars.ContextVar(
    '_SESSION',
)

# Param Spec to represent decorated function parameters
_PT = _t.ParamSpec('_PT')
# TypeVar to represent decorated function return type
_RT = _t.TypeVar('_RT')


def current_session() -> AkeylessSession:
    """Get the session of the backend being run.

    :returns: The session set up by :func:`inject_session`.
    """
    return _SESSION.get()


@_ctx.contextmanager
def _api_client(
    *,
    gateway_url: str = '',
    url: str = '',
    ca_cert: str | None = None,
    **_other_inputs: object,
) -> _abc.Iterator[V2Api]:
    # `url` on the OIDC credential types, `gateway_url` on the others:
    endpoint = (url or gateway_url).rstrip('/')
    if not endpoint:
        raise ValueError('An Akeyless Gateway URL must be set.')
    with CertFiles(ca_cert) as ca_cert_path:
        client_configuration = Configuration(host=endpoint)
        if ca_cert_path:
            client_configuration.ssl_ca_cert = ca_cert_path
            client_configuration.verify_ssl = True
        api_client = ApiClient(client_configuration)
        api_client.user_agent = 'AWX'
        api_client.default_headers['akeylessclienttype'] = 'AWX'
        yield V2Api(api_client)


def _authenticate(
    api: V2Api,
    /,
    *,
    access_id: str = '',
    access_key: str = '',
    workload_identity_token: str = '',
    **_other_inputs: object,
) -> str:
    if not access_id:
        raise ValueError('An Akeyless Access ID must be set.')
    # The controller injects `workload_identity_token` for the OIDC
    # credential types, the others hold a user-supplied `access_key`:
    if workload_identity_token:
        auth_request = Auth(
            access_type='jwt',
            access_id=access_id,
            jwt=workload_identity_token,
        )
    elif access_key:
        auth_request = Auth(access_id=access_id, access_key=access_key)
    else:
        raise ValueError(
            'Either an Access Key or a workload identity token is required '
            'to authenticate with Akeyless.',
        )
    auth_response = api.auth(auth_request)
    if not auth_response.token:
        raise ValueError(
            'Failed to authenticate with Akeyless: no token received.',
        )
    return auth_response.token


@_ctx.contextmanager
def _wrapped_api_errors() -> _abc.Iterator[None]:
    """Surface every Akeyless failure to the caller as ``RuntimeError``."""
    try:
        yield
    except ApiException as api_exc:
        raise RuntimeError(
            f'Akeyless API error: {api_exc.reason} (Status: {api_exc.status})',
        ) from api_exc
    except ValueError as val_err:
        raise RuntimeError(str(val_err)) from val_err


def inject_session(
    decorated_function: _abc.Callable[_PT, _RT],
    /,
) -> _abc.Callable[_PT, _RT]:
    """Authenticate to Akeyless before running a credential backend.

    The decorated backend gets the session from :func:`current_session`
    and receives the authentication inputs in its discarded keyword
    arguments.

    :param decorated_function: The credential backend to wrap.
    :returns: The backend wrapped with Akeyless authentication.
    """

    @_functools.wraps(decorated_function)
    def wrapper(*args: _PT.args, **kwargs: _PT.kwargs) -> _RT:
        # The controller passes every input of the credential type in kwargs:
        auth_inputs = _t.cast('_AuthInputs', kwargs)
        with _wrapped_api_errors(), _api_client(**auth_inputs) as api:
            session_token = _SESSION.set(
                AkeylessSession(api, _authenticate(api, **auth_inputs)),
            )
            try:
                return decorated_function(*args, **kwargs)
            finally:
                _SESSION.reset(session_token)

    return wrapper
