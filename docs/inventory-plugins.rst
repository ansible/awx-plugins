.. _ug_inventories_plugins:

Inventory Plugins
===================

.. index::
   pair: inventories; plugins

Inventory updates use dynamically-generated YAML files which are parsed by their respective inventory plugin. Users can provide the new style inventory plugin config directly to AWX via the inventory source ``source_vars`` for all the following inventory sources:

- :ref:`ug_source_ec2`
- :ref:`ug_source_gce`
- :ref:`ug_source_azure`
- :ref:`ug_source_vmvcenter`
- :ref:`ug_source_satellite`
- :ref:`ug_source_insights`
- :ref:`ug_source_openstack`
- :ref:`ug_source_rhv`
- :ref:`ug_source_rhaap`
- :ref:`ug_source_terraform`
- :ref:`ug_source_ocpv`


Newly created configurations for inventory sources will contain the default plugin configuration values. If you want your newly created inventory sources to match the output of legacy sources, you must apply a specific set of configuration values for that source. To ensure backward compatibility, AWX uses "templates" for each of these sources to force the output of inventory plugins into the legacy format. Refer to :ref:`ir_inv_plugin_templates_reference` section of this guide for each source and their respective templates to help you migrate to the new style inventory plugin output.

``source_vars`` that contain ``plugin: foo.bar.baz`` as a top-level key will be replaced with the appropriate fully-qualified inventory plugin name at runtime based on the ``InventorySource`` source. For example, if ec2 is selected for the ``InventorySource`` then, at run-time, plugin will be set to ``amazon.aws.aws_ec2``.

Inventory sources are not associated with groups. Spawned groups are top-level and may still have child groups, and all of these spawned groups may have hosts. Adding a source to an inventory only applies to standard inventories. Smart inventories inherit their source from the standard inventories they are associated with.

.. _ug_source_ec2:

Amazon Web Services EC2
~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Amazon Web Services

1. To configure an AWS EC2-sourced inventory, select **Amazon EC2** from the Source field.

2. The Create Source window expands with additional fields. Enter the following details:

   - **Credential**: Optionally choose from an existing AWS credential. If AWX is running on an EC2 instance with an assigned IAM Role, the credential may be omitted, and the security credentials from the instance metadata will be used instead. For more information on using IAM Roles, refer to the AWS documentation, `IAM roles for Amazon EC2 <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam- roles-for-amazon-ec2.html>`_.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``aws_ec2`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `aws_ec2 inventory plugin documentation <https://cloud.redhat.com/ansible/automation-hub/repo/published/amazon/aws/content/inventory/aws_ec2>`__.

|Inventories - create source - AWS EC2 example|

.. |Inventories - create source - AWS EC2 example| image:: _static/images/inventories-create-source-AWS-example.png
   :alt: Inventories create source AWS example


.. note::

  If you only use ``include_filters``, the AWS plugin always returns all the hosts. To use this properly, the first condition on the ``or`` must be on ``filters`` and then build the rest of the ``OR`` conditions on a list of ``include_filters``.

.. _ug_source_gce:

Google Compute Engine
~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Google Compute Engine

1. To configure a Google-sourced inventory, select **Google Compute Engine** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing GCE Credential.
|Inventories - create source - GCE example|

.. |Inventories - create source - GCE example| image:: _static/images/inventories-create-source-GCE-example.png
   :alt: Inventories create source Google compute engine example

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``gcp_compute`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `gcp_compute inventory plugin documentation <https://cloud.redhat.com/ansible/automation-hub/repo/published/google/cloud/content/inventory/gcp_compute>`__.


.. _ug_source_azure:

Microsoft Azure Resource Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Microsoft Azure Resource Manager

1. To configure a Azure Resource Manager-sourced inventory, select **Microsoft Azure Resource Manager** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing Azure Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options.

4. Use the **Source Variables** field to override variables used by the  ``azure_rm`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `azure_rm inventory plugin documentation <https://cloud.redhat.com/ansible/automation-hub/repo/published/azure/azcollection/content/inventory/azure_rm>`__.

|Inventories - create source - Azure RM example|

.. |Inventories - create source - Azure RM example| image:: _static/images/inventories-create-source-azurerm-example.png
   :alt: Inventories create source Azure example

.. _ug_source_vmvcenter:

VMware vCenter
~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; VMware vCenter


1. To configure a VMWare-sourced inventory, select **VMware vCenter** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing VMware Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``vmware_inventory`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `vmware_inventory inventory plugin <https://github.com/ansible-collections/community.vmware/blob/main/plugins/inventory/vmware_vm_inventory.py>`__.

  Starting with Ansible 2.9, VMWare properties have changed from lower case to camel-Case. AWX provides aliases for the top-level keys, but lower case keys in nested properties have been discontinued. For a list of valid and supported properties starting with Ansible 2.9, the `list of virtual machine attributes <https://docs.ansible.com/ansible/8/collections/community/vmware/docsite/vmware_scenarios/vmware_inventory_vm_attributes.html>`_ in the Ansible collections documentation.

|Inventories - create source - VMware example|

.. |Inventories - create source - VMWare example| image:: _static/images/inventories-create-source-vmware-example.png
   :alt: Inventories create source VMWare example

.. _ug_source_satellite:

Red Hat Satellite 6
~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Red Hat Satellite 6

1. To configure a Red Hat Satellite-sourced inventory, select **Red Hat Satellite** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing Satellite Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to specify parameters used by the foreman inventory source. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, refer to the `theforeman.foreman.foreman – Foreman inventory source <https://docs.ansible.com/ansible/latest/collections/theforeman/foreman/foreman_inventory.html>`_ in the Ansible documentation.


|Inventories - create source - RH Satellite example|

.. |Inventories - create source - RH Satellite example| image:: _static/images/inventories-create-source-rhsat6-example.png
   :alt: Inventories create source Red Hat Satellite example

If you encounter an issue with AWX inventory not having the "related groups" from Satellite, you might need to define these variables in the inventory source. See the inventory plugins template example for :ref:`ir_plugin_satellite` for detail.


.. _ug_source_insights:

Red Hat Insights
~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Red Hat Insights

1. To configure a Red Hat Insights-sourced inventory, select **Red Hat Insights** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing Insights Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``insights`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `insights inventory plugin <https://cloud.redhat.com/ansible/automation-hub/repo/published/redhat/insights/content/inventory/insights>`__.


|Inventories - create source - RH Insights example|

.. |Inventories - create source - RH Insights example| image:: _static/images/inventories-create-source-insights-example.png
   :alt: Inventories create source Red Hat Insights example

.. _ug_source_openstack:

OpenStack
~~~~~~~~~~~~

.. index::
   pair: inventories; OpenStack


1. To configure an OpenStack-sourced inventory, select **OpenStack** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing OpenStack Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``openstack`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `openstack inventory plugin <https://docs.ansible.com/ansible/latest/collections/openstack/cloud/openstack_inventory.html>`_ in the Ansible collections documentation.

|Inventories - create source - OpenStack example|

.. |Inventories - create source - OpenStack example| image:: _static/images/inventories-create-source-openstack-example.png
   :alt: Inventories create source OpenStack example

.. _ug_source_rhv:

Red Hat Virtualization
~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Red Hat Virtualization

1. To configure a Red Hat Virtualization-sourced inventory, select **Red Hat Virtualization** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing Red Hat Virtualization Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``ovirt`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For a detailed description of these variables, view the `ovirt inventory plugin <https://cloud.redhat.com/ansible/automation-hub/repo/published/redhat/rhv/content/inventory/ovirt>`__.

|Inventories - create source - RHV example|

.. |Inventories - create source - RHV example| image:: _static/images/inventories-create-source-rhv-example.png
   :alt: Inventories create source Red Hat Virtualization example


.. note::

  Red Hat Virtualization (ovirt) inventory source requests are secure by default. To change this default setting, set the key ``ovirt_insecure`` to **true** in ``source_variables``, which is only available from the API details of the inventory source at the ``/api/v2/inventory_sources/N/`` endpoint.

.. _ug_source_rhaap:

Red Hat Ansible Automation Platform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Red Hat Ansible Automation Platform


1. To configure this type of sourced inventory, select **Red Hat Ansible Automation Platform** from the Source field.

2. The Create Source window expands with the required **Credential** field. Choose from an existing Ansible Automation Platform Credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

  .. image:: _static/images/inventories-create-source-rhaap-example.png
   :alt: Inventories create source Red Hat Ansible Automation Platform example

4. Use the **Source Variables** field to override variables used by the ``controller`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two.


.. _ug_source_terraform:

Terraform State
~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; Terraform
   pair: inventory source; Terraform state


This inventory source uses the `terraform_state <https://github.com/ansible-collections/cloud.terraform/blob/main/docs/cloud.terraform.terraform_state_inventory.rst>`_ inventory plugin from the `cloud.terraform <https://github.com/ansible-collections/cloud.terraform>`_ collection. The plugin will parse a terraform state file and add hosts for AWS EC2, GCE, and Azure instances.

1. To configure this type of sourced inventory, select **Terraform State** from the Source field.

2. The Create new source window expands with the required **Credential** field. Choose from an existing Terraform backend credential.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed. For Terraform, enable **Overwrite** and **Update on launch** options.

4. Use the **Source Variables** field to override variables used by the ``terraform`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For more information on these variables, see the `terraform_state <https://github.com/ansible-collections/cloud.terraform/blob/main/docs/cloud.terraform.terraform_state_inventory.rst>`_ file for detail.

  The ``backend_type`` variable is required by the Terraform state inventory plugin. This should match the remote backend configured in the Terraform backend credential, here is an example for an Amazon S3 backend:

  ::

    ---
    backend_type: s3

5. Enter an execution environment in the **Execution Environment** field that contains a Terraform binary. This is required for the inventory plugin to run the Terraform commands that read inventory data from the Terraform state file. Refer to the `Terraform EE readme <https://github.com/ansible-cloud/terraform_ee>`_ that contains an example execution environment configuration with a Terraform binary.

  .. image:: _static/images/inventories-create-source-terraform-example.png
   :alt: Inventories create source Terraform example

6. To add hosts for AWS EC2, GCE, and Azure instances, the Terraform state file in the backend must contain state for resources already deployed to EC2, GCE, or Azure. Refer to each of the Terraform providers' respective documentation to provision instances.


.. _ug_source_ocpv:

OpenShift Virtualization
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   pair: inventories; OpenShift
   pair: inventories; OCP
   pair: inventory source; OpenShift virtualization


This inventory source uses a cluster that is able to deploy OpenShift (OCP) virtualization. In order to configure an OCP virtualization requires a virtual machine deployed in a specific namespace and an OpenShift or Kubernetes API Bearer Token credential.

1. To configure this type of sourced inventory, select **OpenShift Virtualization** from the Source field.
2. The Create new source window expands with the required **Credential** field. Choose from an existing Kubernetes API Bearer Token credential. In this example, the ``cmv2.engineering.redhat.com`` credential is used.

3. You can optionally specify the verbosity, host filter, enabled variable/value, and update options as needed.

4. Use the **Source Variables** field to override variables used by the ``kubernetes`` inventory plugin. Enter variables using either JSON or YAML syntax. Use the radio button to toggle between the two. For more information on these variables, see the `kubevirt.core.kubevirt inventory source <https://kubevirt.io/kubevirt.core/main/plugins/kubevirt.html#parameters>`_ documentation for detail.

  In the example below, the ``connections`` variable is used to specify access to a particular namespace in a cluster.

  ::

    ---
    connections:
    - namespaces:
      - hao-test


  .. image:: _static/images/inventories-create-source-ocpvirt-example.png
   :alt: Inventories create source OpenShift virtualization example

5. Save the configuration and click the **Sync** button to sync the inventory.
