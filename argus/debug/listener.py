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

import multiprocessing.connection as connection


class BasicListener(object):
    """Listener implementation in case the debuger is the BasicDebuger"""
    _PAUSE = 'pause'
    _RESUME = 'resume'

    def __init__(self, config, log, stdout):
        """Initialize and get needed config values to avoid importing util."""
        self._ip = config.ip
        self._port = config.port
        self._authkey = config.authkey
        self._log = log
        self._stdout = stdout

    def _new_listener(self):
        """Returns a Listener according to values given in config."""
        try:
            return connection.Listener((self._ip, self._port),
                                       authkey=self._authkey)
        except connection.AuthenticationError:
            raise self._log.exception("AuthenticationError - Listener creation"
                                      "failed. Check authentication key!")

    def start(self):
        """Starts listening for connections and treat client responses."""
        listener = self._new_listener()
        while True:
            # This will wait until a client connects and the connection will
            # persist until the client closes it.
            conn = listener.accept()
            typec = conn.recv_bytes()
            msg = conn.recv_bytes()
            if typec == self._PAUSE:
                self._stdout.info(msg)
                self._stdout.info('Enter the number of what you want to do:')
                self._stdout.info('1. Continue')
                option = raw_input('Prompt: ')
                if option == '1':
                    self._stdout.info('Argus is resumed!')
                    try:
                        conn.send_bytes(self._RESUME)
                    except ValueError:
                        self._log.exception("ValueError - Message has more "
                                            "than 32MB.")
