# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="assignment, no-untyped-call, no-untyped-def, var-annotated"

import os.path
import stat
import tempfile

from awx_plugins.interfaces._temporary_private_container_api import (  # noqa: WPS436
    get_incontainer_path,
)
from awx_plugins.interfaces._temporary_private_injector_api import (  # noqa: WPS436
    load_injector_callable,
)

import yaml

from awx_plugins.credentials.injectors import _openstack_data


class PluginFileInjector:
    plugin_name = None  # Ansible core name used to reference plugin
    # base injector should be one of None, "managed", or "template"
    # this dictates which logic to borrow from playbook injectors
    base_injector = None
    # every source should have collection, these are for the collection name
    namespace = None
    collection = None
    collection_migration = '2.9'  # Starting with this version, we use collections
    use_fqcn = False  # plugin: name versus plugin: namespace.collection.name

    # TODO: delete this method and update unit tests
    @classmethod
    def get_proper_name(cls) -> str | None:
        if cls.plugin_name is None:
            return None
        return f'{cls.namespace}.{cls.collection}.{cls.plugin_name}'

    @property
    def filename(self) -> str:
        """Inventory filename for using the inventory plugin This is created
        dynamically, but the auto plugin requires this exact naming."""  # noqa: DAR201; FIXME
        return f'{self.plugin_name}.yml'

    def inventory_contents(self, inventory_update, private_data_dir):
        """Returns a string that is the content for the inventory file for the
        inventory plugin."""  # noqa: DAR101, DAR201; FIXME
        return yaml.safe_dump(
            self.inventory_as_dict(
                inventory_update,
                private_data_dir,
            ),
            default_flow_style=False,
            width=1000,
        )

    def inventory_as_dict(self, inventory_update, private_data_dir):
        source_vars = dict(inventory_update.source_vars_dict)  # make a copy
        """None conveys that we should use the user-provided plugin.

        Note that a plugin value of '' should still be overridden.
        """
        if self.plugin_name is not None:
            source_vars['plugin'] = f"""{
                self.namespace
            }.{
                self.collection
            }.{
                self.plugin_name
            }""" if self.use_fqcn else self.plugin_name
        return source_vars

    def build_env(
            self,
            inventory_update,
            env,
            private_data_dir,
            private_data_files,
    ):
        injector_env = self.get_plugin_env(
            inventory_update, private_data_dir, private_data_files,
        )
        env.update(injector_env)
        # All CLOUD_PROVIDERS sources implement as inventory plugin from
        # collection
        env['ANSIBLE_INVENTORY_ENABLED'] = 'auto'
        return env

    def _get_shared_env(
            self,
            inventory_update,
            private_data_dir,
            private_data_files,
    ):  # noqa: DAR101, DAR201; FIXME
        """By default, we will apply the standard managed injectors."""
        if self.base_injector not in {'managed', 'template'}:
            return {}

        credential = inventory_update.get_cloud_credential()
        # some sources may have no credential, specifically ec2
        if credential is None:
            return {}

        injected_env = {
            'INVENTORY_UPDATE_ID': str(
                inventory_update.pk,
            ),  # so injector knows this is inventory
        }

        if self.base_injector == 'managed':
            try:
                inject_credential_into_env = load_injector_callable(
                    inventory_update.source,
                )
            except LookupError:
                pass  # noqa: WPS420
            else:
                inject_credential_into_env(
                    credential,
                    injected_env,
                    private_data_dir,
                )
        elif self.base_injector == 'template':
            safe_env = injected_env.copy()
            args = []
            credential.credential_type.inject_credential(
                credential, injected_env, safe_env, args, private_data_dir,
            )
            # NOTE: safe_env is handled externally to injector class by build_safe_env static method
            # that means that managed injectors must only inject detectable env keys
            # enforcement of this is accomplished by tests
        return injected_env

    def get_plugin_env(
            self,
            inventory_update,
            private_data_dir,
            private_data_files,
    ):
        env = self._get_shared_env(
            inventory_update,
            private_data_dir,
            private_data_files,
        )
        return env

    def build_private_data(self, inventory_update, private_data_dir):
        return self.build_plugin_private_data(
            inventory_update, private_data_dir,
        )

    def build_plugin_private_data(self, inventory_update, private_data_dir):
        return None


class azure_rm(PluginFileInjector):
    plugin_name = 'azure_rm'
    base_injector = 'managed'
    namespace = 'azure'
    collection = 'azcollection'

    def get_plugin_env(self, *args, **kwargs):
        ret = super().get_plugin_env(*args, **kwargs)
        # We need native jinja2 types so that tags can give JSON null value
        ret['ANSIBLE_JINJA2_NATIVE'] = str(True)
        return ret


class ec2(PluginFileInjector):
    plugin_name = 'aws_ec2'
    base_injector = 'managed'
    namespace = 'amazon'
    collection = 'aws'

    def get_plugin_env(self, *args, **kwargs):
        ret = super().get_plugin_env(*args, **kwargs)
        # We need native jinja2 types so that ec2_state_code will give integer
        ret['ANSIBLE_JINJA2_NATIVE'] = str(True)
        return ret


class gce(PluginFileInjector):
    plugin_name = 'gcp_compute'
    base_injector = 'managed'
    namespace = 'google'
    collection = 'cloud'

    def get_plugin_env(self, *args, **kwargs):
        ret = super().get_plugin_env(*args, **kwargs)
        # We need native jinja2 types so that ip addresses can give JSON null
        # value
        ret['ANSIBLE_JINJA2_NATIVE'] = str(True)
        return ret

    def inventory_as_dict(self, inventory_update, private_data_dir):
        ret = super().inventory_as_dict(inventory_update, private_data_dir)
        credential = inventory_update.get_cloud_credential()
        # InventorySource.source_vars take precedence over ENV vars
        if 'projects' not in ret:
            ret['projects'] = [credential.get_input('project', default='')]
        return ret


class vmware(PluginFileInjector):
    plugin_name = 'vmware_vm_inventory'
    base_injector = 'managed'
    namespace = 'community'
    collection = 'vmware'


class openstack(PluginFileInjector):
    plugin_name = 'openstack'
    namespace = 'openstack'
    collection = 'cloud'

    def _get_clouds_dict(self, inventory_update, cred, private_data_dir):
        openstack_data = _openstack_data(cred)

        openstack_data['clouds']['devstack']['private'] = inventory_update.source_vars_dict.get(
            'private', True, )
        ansible_variables = {
            'use_hostnames': True,
            'expand_hostvars': False,
            'fail_on_errors': True,
        }
        provided_count = 0
        for var_name in ansible_variables:
            if var_name in inventory_update.source_vars_dict:
                ansible_variables[var_name] = inventory_update.source_vars_dict[var_name]
                provided_count += 1
        if provided_count:
            # Must we provide all 3 because the user provides any 1 of these??
            # this probably results in some incorrect mangling of the defaults
            openstack_data['ansible'] = ansible_variables
        return openstack_data

    def build_plugin_private_data(self, inventory_update, private_data_dir):
        credential = inventory_update.get_cloud_credential()
        private_data = {'credentials': {}}

        openstack_data = self._get_clouds_dict(
            inventory_update, credential, private_data_dir,
        )
        private_data['credentials'][credential] = yaml.safe_dump(
            openstack_data, default_flow_style=False, allow_unicode=True,
        )
        return private_data

    def get_plugin_env(
            self,
            inventory_update,
            private_data_dir,
            private_data_files,
    ):
        env = super().get_plugin_env(
            inventory_update,
            private_data_dir,
            private_data_files,
        )
        credential = inventory_update.get_cloud_credential()
        cred_data = private_data_files['credentials']
        env['OS_CLIENT_CONFIG_FILE'] = get_incontainer_path(
            cred_data[credential], private_data_dir,
        )
        return env


class rhv(PluginFileInjector):
    """Ovirt uses the custom credential templating, and that is all."""

    plugin_name = 'ovirt'
    base_injector = 'template'
    initial_version = '2.9'
    namespace = 'ovirt'
    collection = 'ovirt'
    use_fqcn = True


class rhv_supported(PluginFileInjector):
    """Ovirt uses the custom credential templating, and that is all."""

    plugin_name = 'ovirt'
    base_injector = 'template'
    initial_version = '2.9'
    namespace = 'redhat'
    collection = 'rhv'
    use_fqcn = True


class satellite6(PluginFileInjector):
    plugin_name = 'foreman'
    namespace = 'theforeman'
    collection = 'foreman'
    use_fqcn = True

    def get_plugin_env(
            self,
            inventory_update,
            private_data_dir,
            private_data_files,
    ):
        # this assumes that this is merged
        # https://github.com/ansible/ansible/pull/52693
        credential = inventory_update.get_cloud_credential()
        ret = super().get_plugin_env(
            inventory_update,
            private_data_dir,
            private_data_files,
        )
        if credential:
            ret['FOREMAN_SERVER'] = credential.get_input('host', default='')
            ret['FOREMAN_USER'] = credential.get_input('username', default='')
            ret['FOREMAN_PASSWORD'] = credential.get_input(
                'password', default='',
            )
        return ret


class satellite6_supported(PluginFileInjector):
    plugin_name = 'foreman'
    namespace = 'redhat'
    collection = 'satellite'
    use_fqcn = True

    def get_plugin_env(
            self,
            inventory_update,
            private_data_dir,
            private_data_files,
    ):
        # this assumes that this is merged
        # https://github.com/ansible/ansible/pull/52693
        credential = inventory_update.get_cloud_credential()
        ret = super().get_plugin_env(
            inventory_update,
            private_data_dir,
            private_data_files,
        )
        if credential:
            ret['FOREMAN_SERVER'] = credential.get_input('host', default='')
            ret['FOREMAN_USER'] = credential.get_input('username', default='')
            ret['FOREMAN_PASSWORD'] = credential.get_input(
                'password', default='',
            )
        return ret


class terraform(PluginFileInjector):
    plugin_name = 'terraform_state'
    namespace = 'cloud'
    collection = 'terraform'
    use_fqcn = True

    def inventory_as_dict(self, inventory_update, private_data_dir):
        ret = super().inventory_as_dict(inventory_update, private_data_dir)
        credential = inventory_update.get_cloud_credential()
        config_cred = credential.get_input('configuration')
        if config_cred:
            handle, path = tempfile.mkstemp(
                dir=os.path.join(private_data_dir, 'env'),
            )
            with os.fdopen(handle, 'w') as f:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
                f.write(config_cred)
            ret['backend_config_files'] = get_incontainer_path(
                path, private_data_dir,
            )
        return ret

    def build_plugin_private_data(self, inventory_update, private_data_dir):
        credential = inventory_update.get_cloud_credential()

        private_data = {'credentials': {}}
        gce_cred = credential.get_input('gce_credentials', default=None)
        if gce_cred:
            private_data['credentials'][credential] = gce_cred
        return private_data

    def get_plugin_env(
            self,
            inventory_update,
            private_data_dir,
            private_data_files,
    ):
        env = super().get_plugin_env(
            inventory_update,
            private_data_dir,
            private_data_files,
        )
        credential = inventory_update.get_cloud_credential()
        cred_data = private_data_files['credentials']
        if credential in cred_data:
            env['GOOGLE_BACKEND_CREDENTIALS'] = get_incontainer_path(
                cred_data[credential], private_data_dir,
            )
        return env


class controller(PluginFileInjector):
    # TODO: relying on routing for now, update after EEs pick up revised
    # collection
    plugin_name = 'tower'
    base_injector = 'template'
    namespace = 'awx'
    collection = 'awx'


class controller_supported(PluginFileInjector):
    # TODO: relying on routing for now, update after EEs pick up revised
    # collection
    plugin_name = 'tower'
    base_injector = 'template'
    namespace = 'ansible'
    collection = 'controller'


class insights(PluginFileInjector):
    plugin_name = 'insights'
    base_injector = 'template'
    namespace = 'redhatinsights'
    collection = 'insights'
    use_fqcn = True


class insights_supported(PluginFileInjector):
    plugin_name = 'insights'
    base_injector = 'template'
    namespace = 'redhat'
    collection = 'insights'
    use_fqcn = True


class openshift_virtualization(PluginFileInjector):
    plugin_name = 'kubevirt'
    base_injector = 'template'
    namespace = 'kubevirt'
    collection = 'core'
    use_fqcn = True


class openshift_virtualization_supported(PluginFileInjector):
    plugin_name = 'kubevirt'
    base_injector = 'template'
    namespace = 'redhat'
    collection = 'openshift_virtualization'
    use_fqcn = True


class constructed(PluginFileInjector):
    plugin_name = 'constructed'
    namespace = 'ansible'
    collection = 'builtin'

    def build_env(self, *args, **kwargs):
        env = super().build_env(*args, **kwargs)
        # Enable script inventory plugin so we pick up the script files from
        # source inventories
        env['ANSIBLE_INVENTORY_ENABLED'] += ',script'
        env['ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED'] = 'True'
        return env
