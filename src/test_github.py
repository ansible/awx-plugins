from github import Github, Auth
import pem


url = 'https://github.com'
app_id=1121547
installation_id=60185608
ssh_keyfile='/home/arestlel/Downloads/arestlel-github-app-ansible.2025-01-23.private-key.pem'
jwt_expiry=600


# Read the private key from the file
# private_key=pem.parse_file(ssh_keyfile)


with open(ssh_keyfile, 'r') as file:
    private_key = file.read()

token_permissions = {
}
auth = Auth.AppAuth(app_id, private_key).get_installation_auth(installation_id, None)
g = Github(auth=auth)
print (auth.token)