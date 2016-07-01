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

import collections
import itertools

import six


_SENTINEL = object()
BOOL = 'bool'
INT = 'int'


class _ConfigParser(six.moves.configparser.ConfigParser):
    def getlist(self, section, option):
        value = self.get(section, option)
        values = value.splitlines()
        iters = (map(str.strip, filter(None, value.split(",")))
                 for value in values)
        return list(itertools.chain.from_iterable(iters))

    # Don't lowercase.
    optionxform = str


def _get_default(parser, section, option, default=None, parser_type=None):
    try:
        if parser_type == BOOL:
            return parser.getboolean(section, option)
        elif parser_type == INT:
            return parser.getint(section, option)
        else:
            return parser.get(section, option)
    except six.moves.configparser.NoOptionError:
        return default


class ConfigurationParser(object):
    """A parser class which knows how to parse argus configurations."""

    RESOURCES_LINK = ('https://raw.githubusercontent.com/cloudbase/'
                      'cloudbase-init-ci/master/argus/resources')

    def __init__(self, filename):
        self._filename = filename
        self._parser = _ConfigParser()
        self._parser.read(self._filename)

    @property
    def argus(self):
        # Get the argus section
        argus = collections.namedtuple('argus',
                                       'resources pause '
                                       'file_log log_format dns_nameservers '
                                       'output_directory build arch '
                                       'patch_install git_command')
        resources = _get_default(
            self._parser, 'argus', 'resources', self.RESOURCES_LINK)
        pause = self._parser.getboolean('argus', 'pause')
        file_log = _get_default(self._parser, 'argus', 'file_log')
        log_format = _get_default(self._parser, 'argus', 'log_format')
        dns_nameservers = _get_default(
            self._parser, 'argus', 'dns_nameservers',
            ['8.8.8.8', '8.8.4.4'])
        if not isinstance(dns_nameservers, list):
            # pylint: disable=no-member
            dns_nameservers = dns_nameservers.split(",")
        output_directory = _get_default(self._parser, 'argus', 'output_directory')
        build = _get_default(self._parser, 'argus', 'build', 'Beta')
        arch = _get_default(self._parser, 'argus', 'arch', 'x64')
        patch_install = _get_default(self._parser, 'argus', 'patch_install')
        git_command = _get_default(self._parser, 'argus', 'git_command')

        return argus(resources, pause, file_log, log_format,
                     dns_nameservers, output_directory, build, arch,
                     patch_install, git_command)

    @property
    def cloudbaseinit(self):
        cloudbaseinit = collections.namedtuple(
            'cloudbaseinit',
            'created_user group')

        group = self._parser.get('cloudbaseinit', 'group')
        created_user = self._parser.get('cloudbaseinit', 'created_user')

        return cloudbaseinit(created_user, group)

    @property
    def openstack(self):
        openstack = collections.namedtuple(
            'openstack',
            'image_ref flavor_ref image_username image_password '
            'image_os_type require_sysprep')
        image_ref = self._parser.get('openstack', 'image_ref')
        flavor_ref = self._parser.get('openstack', 'flavor_ref')
        image_username = self._parser.get('openstack', 'image_username')
        image_password = self._parser.get('openstack', 'image_password')
        image_os_type = self._parser.get('openstack', 'image_os_type')
        require_sysprep = self._parser.get('openstack', 'require_sysprep')

        return openstack(image_ref, flavor_ref, image_username,
                         image_password, image_os_type, require_sysprep)

    @property
    def debug(self):
        debug = collections.namedtuple(
            'debug',
            'flag ip port authkey')
        flag = _get_default(self._parser, 'debug', 'flag', False, BOOL)
        ip = _get_default(self._parser, 'debug', 'ip', '127.0.0.1')
        port = _get_default(self._parser, 'debug', 'port', 5555, INT)
        authkey = _get_default(self._parser, 'debug', 'authkey', 'authkey')

        return debug(flag, ip, port, authkey)

    @property
    def conf(self):
        conf = collections.namedtuple(
            'conf', 'argus cloudbaseinit openstack debug')
        return conf(self.argus, self.cloudbaseinit, self.openstack, self.debug)
