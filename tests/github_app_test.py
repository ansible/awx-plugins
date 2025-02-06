import pytest
from unittest import mock
from awx_plugins.credentials import github_app
from github import Auth

JWT_EXPIRY_DEFAULT = 600

def test_github_app_missing_parameters() -> None:
    """Test that missing parameters raise an exception."""
    with pytest.raises(ValueError, match=r'Missing Parameter: \[.*\]'):
        github_app.github_app_backend()

    with pytest.raises(ValueError, match=r"Missing Parameter: \['GitHub URL'\]"):
        github_app.github_app_backend(
            app_id='123', install_id='456', ssh_key_data='key',
        )


def test_github_app_invalid_app_id_and_install_id() -> None:
    """Test that non-integer app_id and install_id raise an exception."""
    with pytest.raises(ValueError, match=r'App ID and Installation ID must be integers .*invalid literal for int\(\) with base 10: .*'):
        github_app.github_app_backend(
            github_url='https://github.com',
            app_id='invalid',
            install_id='invalid',
            ssh_key_data='key',
        )


def test_github_app_invalid_jwt_expiry() -> None:
    """Test that non-integer JWT expiry raises an exception."""
    with pytest.raises(ValueError, match=r'JWT Expiry must be an integer invalid'):

        github_app.github_app_backend(
            github_url='https://github.com',
            app_id='123',
            install_id='456',
            ssh_key_data='key',
            jwt_expiry='invalid',
        )

def test_github_app_github_authentication() -> None:
    """Test successful GitHub authentication."""
    
    # Mock the AppInstallationAuth to be returned
    mock_auth_instance = mock.MagicMock(spec=Auth.AppInstallationAuth)
    mock_auth_instance.token = 'example-token'
    
    # Mock AppAuth and get_installation_auth() to return our mock instance
    mock_app_auth = mock.MagicMock(spec=Auth.AppAuth)
    mock_app_auth.get_installation_auth.return_value = mock_auth_instance

    with mock.patch.object(Auth, 'AppAuth', return_value=mock_app_auth):
        token = github_app.github_app_backend(
            github_url='https://github.com',
            app_id='123',
            install_id='456',
            ssh_key_data='example-key',
            jwt_expiry=JWT_EXPIRY_DEFAULT,
        )
        assert token == 'example-token'
