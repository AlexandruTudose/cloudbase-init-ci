# Copyright 2015 Cloudbase Solutions Srl
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

from argus import util


class WindowsBackendMixin(object):
    """Mixin backend tailored for interacting with Windows."""

    # pylint: disable=unused-argument
    def get_remote_client(self, username=None, password=None,
                          protocol='http', **kwargs):
        if username is None:
            username = self._conf.openstack.image_username
        if password is None:
            password = self._conf.openstack.image_password
        return util.WinRemoteClient(self._floating_ip['ip'],
                                    username, password,
                                    transport_protocol=protocol)

    remote_client = util.cached_property(get_remote_client, 'remote_client')
