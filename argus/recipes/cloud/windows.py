# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Windows cloudbaseinit recipes."""

import ntpath
import os

import six

from argus import exceptions
from argus.introspection.cloud import windows as introspection
from argus.recipes.cloud import base
from argus import util

LOG = util.get_logger()

# Default values for an instance under booting step.
COUNT = 20
DELAY = 20
_CBINIT_REPO = "https://github.com/openstack/cloudbase-init"


class CloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    """Recipe for preparing a Windows instance."""

    def wait_for_boot_completion(self):
        LOG.info("Waiting for first boot completion...")
        self._backend.remote_client.manager.wait_boot_completion()

    def execution_prologue(self):
        LOG.info("Retrieve common module for proper script execution.")

        resource_location = "windows/common.psm1"
        self._backend.remote_client.manager.download_resource(
            resource_location=resource_location, location=r'C:\common.psm1')

    def get_installation_script(self):
        """Get instalation script for CloudbaseInit."""
        self._backend.remote_client.manager.get_installation_script()

    def install_cbinit(self, service_type):
        """Proceed on checking if cloudbase-init should be installed."""
        try:
            cbdir = introspection.get_cbinit_dir(self._execute)
        except exceptions.ArgusError:
            self._backend.remote_client.manager.install_cbinit(service_type)
            self._grab_cbinit_installation_log()
        else:
            # If the directory already exists, we won't be installing Cb-init.
            LOG.info("Cloudbase-init is already installed, skipping installation.")

    def _grab_cbinit_installation_log(self):
        """Obtain the installation logs."""
        LOG.info("Obtaining the installation logs.")
        if not self._conf.argus.output_directory:
            LOG.warning("The output directory wasn't given, "
                        "the log will not be grabbed.")
            return

        content = self._backend.remote_client.read_file("C:\\installation.log")
        log_template = "installation-{}.log".format(
            self._backend.instance_server()['id'])

        path = os.path.join(self._conf.argus.output_directory, log_template)
        with open(path, 'w') as stream:
            stream.write(content)

    def replace_install(self):
        """Replace the cb-init installed files with the downloaded ones.

        For the same file names, there will be a replace. The new ones
        will just be added and the other files will be left there.
        So it's more like an update.
        """
        link = self._conf.argus.patch_install
        if not link:
            return

        LOG.info("Replacing cloudbaseinit's files...")

        LOG.debug("Download and extract installation bundle.")
        if link.startswith("\\\\"):
            cmd = 'copy "{}" "C:\\install.zip"'.format(link)
            self._execute(cmd, command_type=util.CMD)
        else:
            location = r'C:\install.zip'
            self._backend.remote_client.manager.download(
                uri=link, location=location)
        cmds = [
            "Add-Type -A System.IO.Compression.FileSystem",
            "[IO.Compression.ZipFile]::ExtractToDirectory("
            "'C:\\install.zip', 'C:\\install')"
        ]
        cmd = '{}'.format("; ".join(cmds))
        self._execute(cmd, command_type=util.POWERSHELL)

        LOG.debug("Replace old files with the new ones.")
        cbdir = introspection.get_cbinit_dir(self._execute)
        self._execute('xcopy /y /e /q "C:\\install\\Cloudbase-Init"'
                      ' "{}"'.format(cbdir), command_type=util.CMD)

    def replace_code(self):
        """Replace the code of cloudbaseinit."""
        if not self._conf.argus.git_command:
            # Nothing to replace.
            return

        LOG.info("Replacing cloudbaseinit's code...")

        LOG.info("Getting cloudbase-init location...")
        # Get cb-init python location.
        python_dir = introspection.get_python_dir(self._execute)

        # Remove everything from the cloudbaseinit installation.
        LOG.info("Removing recursively cloudbaseinit...")
        cloudbaseinit = ntpath.join(
            python_dir,
            "Lib",
            "site-packages",
            "cloudbaseinit")
        self._execute('rmdir "{}" /S /q'.format(cloudbaseinit),
                      command_type=util.CMD)

        # Clone the repo
        LOG.info("Cloning the cloudbaseinit repo...")
        self._backend.remote_client.manager.git_clone(
            repo_url=_CBINIT_REPO,
            location=r"C:\cloudbaseinit")

        # Run the command provided at cli.
        LOG.info("Applying cli patch...")
        self._execute("cd C:\\cloudbaseinit && {}".format(
            self._conf.argus.git_command), command_type=util.CMD)

        # Replace the code, by moving the code from cloudbaseinit
        # to the installed location.
        LOG.info("Replacing code...")
        self._execute('Copy-Item C:\\cloudbaseinit\\cloudbaseinit '
                      '\'{}\' -Recurse'.format(cloudbaseinit),
                      command_type=util.POWERSHELL)

        # Autoinstall packages from the new requirements.txt
        python = ntpath.join(python_dir, "python.exe")
        command = '"{}" -m pip install -r C:\\cloudbaseinit\\requirements.txt'
        self._execute(command.format(python), command_type=util.CMD)

    def pre_sysprep(self):
        """Disable first_logon_behaviour for testing purposes.

        Because first_logon_behaviour will control how the password
        should work on next logon, we could have troubles in tests,
        so this is always disabled, excepting tests which sets
        it manual to whatever they want.
        """
        introspection.set_config_option(
            option="first_logon_behaviour", value="no",
            execute_function=self._execute)

        # Patch the installation of cloudbaseinit in order to create
        # a file when the execution ends. We're doing this instead of
        # monitoring the service, because on some OSes, just checking
        # if the service is stopped leads to errors, due to the
        # fact that the service starts later on.
        python_dir = introspection.get_python_dir(self._execute)
        cbinit = ntpath.join(python_dir, 'Lib', 'site-packages',
                             'cloudbaseinit')

        # Get the shell patching script and patch the installation.
        resource_location = "windows/patch_shell.ps1"
        params = r' "{}"'.format(cbinit)
        self._backend.remote_client.manager.execute_powershell_resource_script(
            resource_location=resource_location, parameters=params)

        # Prepare Something specific for the OS
        self._backend.remote_client.manager.specific_prepare()

    def sysprep(self):
        """Prepare the instance for the actual tests, by running sysprep."""
        LOG.info("Running sysprep...")

        self._backend.remote_client.manager.sysprep()

    def wait_cbinit_finalization(self):
        paths = [
            r"C:\cloudbaseinit_unattended",
            r"C:\cloudbaseinit_normal"]

        LOG.debug("Check the heartbeat patch ...")
        self._backend.remote_client.manager.check_cbinit_service(
            searched_paths=paths)

        LOG.debug("Wait for the CloudBase Initit service to stop ...")
        self._backend.remote_client.manager.wait_cbinit_service()


class CloudbaseinitScriptRecipe(CloudbaseinitRecipe):
    """A recipe which adds support for testing .exe scripts."""

    def pre_sysprep(self):
        super(CloudbaseinitScriptRecipe, self).pre_sysprep()
        LOG.info("Doing last step before sysprepping.")

        resource_location = "windows/test_exe.exe"
        location = r"C:\Scripts\test_exe.exe"
        self._backend.remote_client.manager.download_resource(
            resource_location=resource_location, location=location)


class CloudbaseinitCreateUserRecipe(CloudbaseinitRecipe):
    """A recipe for creating the user created by cloudbaseinit.

    The purpose is to use this recipe for testing that cloudbaseinit
    works, even when the user which should be created already exists.
    """

    def pre_sysprep(self):
        super(CloudbaseinitCreateUserRecipe, self).pre_sysprep()
        LOG.info("Creating the user %s...",
                 self._conf.cloudbaseinit.created_user)

        resource_location = "windows/create_user.ps1"
        params = r" -user {}".format(self._conf.cloudbaseinit.created_user)
        self._backend.remote_client.manager.execute_powershell_resource_script(
            resource_location=resource_location, parameters=params)


class BaseNextLogonRecipe(CloudbaseinitRecipe):
    """Useful for testing the next logon behaviour."""

    behaviour = None

    def pre_sysprep(self):
        super(BaseNextLogonRecipe, self).pre_sysprep()

        introspection.set_config_option(
            option="first_logon_behaviour",
            value=self.behaviour,
            execute_function=self._execute)


class AlwaysChangeLogonPasswordRecipe(BaseNextLogonRecipe):
    """Always change the password at next logon."""

    behaviour = 'always'


class ClearPasswordLogonRecipe(BaseNextLogonRecipe):
    """Change the password at next logon if the password is from metadata."""

    behaviour = 'clear_text_injected_only'


class CloudbaseinitMockServiceRecipe(CloudbaseinitRecipe):
    """A recipe for patching the cloudbaseinit's conf with a custom server."""

    config_entry = None
    pattern = "{}"

    def pre_sysprep(self):
        super(CloudbaseinitMockServiceRecipe, self).pre_sysprep()
        LOG.info("Inject guest IP for mocked service access.")

        # Append service IP as a config option.
        address = self.pattern.format(util.get_local_ip())
        introspection.set_config_option(option=self.config_entry,
                                        value=address,
                                        execute_function=self._execute)


class CloudbaseinitEC2Recipe(CloudbaseinitMockServiceRecipe):
    """Recipe for EC2 metadata service mocking."""

    config_entry = "ec2_metadata_base_url"
    pattern = "http://{}:2000/"


class CloudbaseinitCloudstackRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Cloudstack metadata service mocking."""

    config_entry = "cloudstack_metadata_ip"
    pattern = "{}:2001"

    def pre_sysprep(self):
        super(CloudbaseinitCloudstackRecipe, self).pre_sysprep()

        python_dir = introspection.get_python_dir(self._execute)
        cbinit = ntpath.join(python_dir, 'Lib', 'site-packages',
                             'cloudbaseinit')

        # Install mock
        python = ntpath.join(python_dir, "python.exe")
        command = '"{}" -m pip install mock'
        self._execute(command.format(python), command_type=util.CMD)

        # Get the cloudstack patching script and patch the installation.
        resource_location = "windows/patch_cloudstack.ps1"
        params = r'"{}"'.format(cbinit)
        self._backend.remote_client.manager.execute_powershell_resource_script(
            resource_location=resource_location, parameters=params)


class CloudbaseinitMaasRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Maas metadata service mocking."""

    config_entry = "maas_metadata_url"
    pattern = "http://{}:2002"

    def pre_sysprep(self):
        super(CloudbaseinitMaasRecipe, self).pre_sysprep()

        required_fields = (
            "maas_oauth_consumer_key",
            "maas_oauth_consumer_secret",
            "maas_oauth_token_key",
            "maas_oauth_token_secret",
        )

        for field in required_fields:
            introspection.set_config_option(option=field, value="secret",
                                            execute_function=self._execute)


class CloudbaseinitWinrmRecipe(CloudbaseinitCreateUserRecipe):
    """A recipe for testing the WinRM configuration plugin."""

    def pre_sysprep(self):
        super(CloudbaseinitWinrmRecipe, self).pre_sysprep()
        introspection.set_config_option(
            option="plugins",
            value="cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin",
            execute_function=self._execute)


class CloudbaseinitHTTPRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for http metadata service mocking."""

    config_entry = "metadata_base_url"
    pattern = "http://{}:2003/"


class CloudbaseinitKeysRecipe(CloudbaseinitHTTPRecipe,
                              CloudbaseinitCreateUserRecipe):
    """Recipe that facilitates x509 certificates and public keys testing."""

    def pre_sysprep(self):
        super(CloudbaseinitKeysRecipe, self).pre_sysprep()
        introspection.set_config_option(
            option="plugins",
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin,"
                  "cloudbaseinit.plugins.windows.setuserpassword."
                  "SetUserPasswordPlugin,"
                  "cloudbaseinit.plugins.common.sshpublickeys."
                  "SetUserSSHPublicKeysPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin,"
                  "cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin",
            execute_function=self._execute)


class CloudbaseinitLocalScriptsRecipe(CloudbaseinitRecipe):
    """Recipe for testing local scripts return codes."""

    def pre_sysprep(self):
        super(CloudbaseinitLocalScriptsRecipe, self).pre_sysprep()
        LOG.info("Download reboot-required local script.")

        resource_location = "windows/reboot.cmd"
        self._backend.remote_client.manager.download_resource(
            resource_location=resource_location,
            location=r'C:\Scripts\reboot.cmd')


class CloudbaseinitImageRecipe(CloudbaseinitRecipe):
    """Calibrate already sys-prepared cloudbase-init images."""

    def wait_cbinit_finalization(self):
        cbdir = introspection.get_cbinit_dir(self._execute)
        paths = [ntpath.join(cbdir, "log", name)
                 for name in ["cloudbase-init-unattend.log",
                              "cloudbase-init.log"]]
        self._wait_cbinit_finalization(searched_paths=paths)

    def prepare(self, service_type=None, **kwargs):
        LOG.info("Preparing already syspreped instance...")
        self.execution_prologue()

        if self._conf.argus.pause:
            six.moves.input("Press Enter to continue...")

        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance.")
