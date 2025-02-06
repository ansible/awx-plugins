import pytest
from unittest import mock
from awx_plugins.credentials import github_app

def test_github_app_missing_parameters() -> None:
    """Test that missing parameters raise an exception."""
    with pytest.raises(Exception, match='Missing Parameter'):
        github_app.github_app_backend()

    with pytest.raises(Exception, match=r"Missing Parameter: \['GitHub URL'\]"):
        github_app.github_app_backend(
            app_id='123', install_id='456', ssh_key_data='key',
        )


def test_github_app_invalid_app_id_and_install_id() -> None:
    """Test that non-integer app_id and install_id raise an exception."""
    with pytest.raises(Exception, match='App and Installation ID not integers'):
        github_app.github_app_backend(
            github_url='https://github.com',
            app_id='invalid',
            install_id='invalid',
            ssh_key_data='key',
        )


def test_github_app_invalid_jwt_expiry() -> None:
    """Test that non-integer JWT expiry raises an exception."""
    with pytest.raises(Exception, match='JWT Expiry must be an integer'):
        github_app.github_app_backend(
            github_url='https://github.com',
            app_id='123',
            install_id='456',
            ssh_key_data='key',
            jwt_expiry='invalid',
        )


def test_github_app_github_authentication() -> None:
    """Test successful GitHub authentication."""
    mock_auth = mock.MagicMock()
    mock_auth.get_installation_auth.return_value.token = 'example-token'

    with mock.patch.object(Auth, 'AppAuth', return_value=mock_auth):
        token = github_app.github_app_backend(
            github_url='https://github.com',
            app_id='123',
            install_id='456',
            ssh_key_data='example-key',
            jwt_expiry=JWT_EXPIRY_DEFAULT,
        )
        assert token == 'example-token'
