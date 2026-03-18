"""Tests for GitHub App Installation access token extraction plugin."""

from typing import TypedDict

import pytest
from pytest_mock import MockerFixture

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    RSAPublicKey,
    generate_private_key,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from github.Auth import AppInstallationAuth
from github.Consts import DEFAULT_JWT_ALGORITHM
from github.GithubException import (
    BadAttributeException,
    GithubException,
    UnknownObjectException,
)
from jwt import decode as decode_jwt

from awx_plugins.credentials import github_app as gh_app_plugin_mod


RSA_PUBLIC_EXPONENT = 65_537  # noqa: WPS303
MINIMUM_RSA_KEY_SIZE = 1024  # the lowest value chosen for performance in tests
TEST_APP_ID = 123


@pytest.fixture(scope='module')
def rsa_private_key() -> RSAPrivateKey:
    """Generate an RSA private key."""
    return generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=MINIMUM_RSA_KEY_SIZE,  # would be 4096 or higher in production
        backend=default_backend(),
    )


@pytest.fixture(scope='module')
def rsa_public_key(rsa_private_key: RSAPrivateKey) -> RSAPublicKey:
    """Extract a public key out of the private one."""
    return rsa_private_key.public_key()


@pytest.fixture(scope='module')
def rsa_private_key_bytes(rsa_private_key: RSAPrivateKey) -> bytes:
    r"""Generate an unencrypted PKCS#1 formatted RSA private key.

    Encoded as PEM-bytes.

    This is what the GitHub-downloaded PEM files contain.

    Ref: https://developer.github.com/apps/building-github-apps/\
         authenticating-with-github-apps/
    """
    return rsa_private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.TraditionalOpenSSL,  # A.K.A. PKCS#1
        encryption_algorithm=NoEncryption(),
    )


@pytest.fixture(scope='module')
def rsa_private_key_str(rsa_private_key_bytes: bytes) -> str:
    """Return private key as an instance of string."""
    return rsa_private_key_bytes.decode('utf-8')


@pytest.fixture(scope='module')
def rsa_public_key_bytes(rsa_public_key: RSAPublicKey) -> bytes:
    """Return a PKCS#1 formatted RSA public key encoded as PEM."""
    return rsa_public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.PKCS1,
    )


class AppInstallIds(TypedDict):
    """Schema for augmented extractor function keyword args."""

    app_or_client_id: str
    install_id: str


@pytest.mark.parametrize(
    (
        'github_exception',
        'transformed_exception',
        'error_msg',
    ),
    (
        (
            BadAttributeException(
                '',
                {},
                Exception(),
            ),
            RuntimeError,
            (
                r'^Broken GitHub @ https://github\.com with '
                r'app_or_client_id: 123, install_id: 456\. It is a bug, '
                'please report it to the '
                r"developers\.\n\n\('', \{\}, Exception\(\)\)$"
            ),
        ),
        (
            GithubException(-1),
            RuntimeError,
            (
                '^An unexpected error happened while talking to GitHub API '
                r'@ https://github\.com '
                r'\(app_or_client_id: 123, install_id: 456\)\. '
                r'Is the app or client ID correct\? '
                r'And the private RSA key\? '
                r'See https://docs\.github\.com/rest/reference/apps'
                r'#create-an-installation-access-token-for-an-app\.'
                r'\n\n-1$'
            ),
        ),
        (
            UnknownObjectException(-1),
            ValueError,
            (
                '^Failed to retrieve a GitHub installation token from '
                r'https://github\.com using '
                r'app_or_client_id: 123, install_id: 456\. '
                r'Is the app installed\? See '
                r'https://docs\.github\.com/rest/reference/apps'
                r'#create-an-installation-access-token-for-an-app\.'
                r'\n\n-1$'
            ),
        ),
    ),
    ids=(
        'github-broken',
        'unexpected-error',
        'no-install',
    ),
)
def test_github_app_api_errors(
    mocker: MockerFixture,
    github_exception: Exception,
    transformed_exception: type[Exception],
    error_msg: str,
) -> None:
    """Test successful GitHub authentication."""
    application_id = 123
    installation_id = 456

    mocker.patch.object(
        gh_app_plugin_mod.Auth.AppInstallationAuth,
        'token',
        new_callable=mocker.PropertyMock,
        side_effect=github_exception,
    )

    with pytest.raises(transformed_exception, match=error_msg):
        gh_app_plugin_mod.extract_github_app_install_token(
            github_api_url='https://github.com',
            app_or_client_id=application_id,
            install_id=installation_id,
            private_rsa_key='key',
        )


class _FakeAppInstallationAuth(AppInstallationAuth):
    @property
    def token(self: '_FakeAppInstallationAuth') -> str:
        return 'token-sentinel'


@pytest.mark.parametrize(
    'application_or_client_id',
    (
        pytest.param(TEST_APP_ID, id='app-id-int'),
        pytest.param(str(TEST_APP_ID), id='app-id-str'),
        pytest.param('Iv1.aaaaaaaaaaaaaaaa', id='client-id-iv1-legacy-format'),
        pytest.param('Iv2aaaaaaaaaaaaaaaa', id='client-id-iv2-new-format'),
        pytest.param(
            'Iv10aaaaaaaaaaaaaaaa',
            id='client-id-iv10-double-digit-version',
        ),
        pytest.param('Iv100.aaaaaaaaaaaaaaaa', id='client-id-iv100-with-dot'),
        pytest.param('Iv23likIfIXeZTb5GCAA', id='client-id-iv23-real-example'),
    ),
)
@pytest.mark.parametrize(
    'installation_id',
    (456, '456'),
    ids=('install-id-int', 'install-id-str'),
)
@pytest.mark.filterwarnings(
    'ignore:The RSA key is '  # noqa: ISC004  # intentional
    f'{MINIMUM_RSA_KEY_SIZE} bits long, which is below the minimum '
    'recommended size of 2048 bits. See NIST SP 800-131A.:'
    'jwt.warnings.InsecureKeyLengthWarning',
)
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_github_app_github_authentication(  # noqa: WPS211
    application_or_client_id: int | str,
    installation_id: int | str,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key_str: str,
    rsa_public_key_bytes: bytes,
) -> None:
    """Test successful GitHub authentication."""
    monkeypatch.setattr(
        gh_app_plugin_mod.Auth,
        'AppInstallationAuth',
        _FakeAppInstallationAuth,
    )

    get_installation_auth_spy = mocker.spy(
        gh_app_plugin_mod.Auth,
        'AppInstallationAuth',
    )
    github_initializer_spy = mocker.spy(gh_app_plugin_mod, 'Github')

    token = gh_app_plugin_mod.extract_github_app_install_token(
        github_api_url='https://github.com',
        app_or_client_id=application_or_client_id,
        install_id=installation_id,
        private_rsa_key=rsa_private_key_str,
    )

    observed_pygithub_obj = github_initializer_spy.spy_return
    observed_gh_install_auth_obj = get_installation_auth_spy.spy_return
    # pylint: disable-next=protected-access
    signed_jwt = observed_gh_install_auth_obj._app_auth.token  # noqa: WPS437

    assert token == 'token-sentinel'

    assert observed_pygithub_obj.requester.base_url == 'https://github.com'

    assert observed_gh_install_auth_obj.installation_id == int(installation_id)
    assert isinstance(observed_gh_install_auth_obj, _FakeAppInstallationAuth)

    # NOTE: The `decode_jwt()` call asserts that no
    # NOTE: `jwt.exceptions.InvalidSignatureError()` exception gets raised
    # NOTE: which would indicate incorrect RSA key or corrupted payload if
    # NOTE: that was to happen. This verifies that JWT is signed with the
    # NOTE: private RSA key we passed by using its public counterpart.
    decode_jwt(
        signed_jwt,
        key=rsa_public_key_bytes,
        algorithms=[DEFAULT_JWT_ALGORITHM],
        options={
            'require': ['exp', 'iat', 'iss'],
            'strict_aud': False,
            'verify_aud': True,
            'verify_exp': True,
            'verify_signature': True,
            'verify_nbf': True,
        },
        audience=None,  # GH App JWT don't set the audience claim
        issuer=str(application_or_client_id),
        leeway=0.001,  # noqa: WPS432
    )
