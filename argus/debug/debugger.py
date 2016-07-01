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
import abc
import multiprocessing.connection as connection
import os
import six

from functools import wraps


@six.add_metaclass(abc.ABCMeta)
class BaseDebugger(object):
    """Abstract class for debugger.

    Any debugger should at least have a pause method implemented
    and actions before and after a function is executed.

    Any debugger should inherit from this one.
    """

    def __init__(self, config, log):
        """Initilaize and get needed the needed config values.

        Passing config as a parameter avoids the need of importing util.
        """
        self._ip = config.ip
        self._port = config.port
        self._authkey = config.authkey
        self._log = log

    @abc.abstractmethod
    def pause(self):
        """Basic action to interrupt execution."""
        pass

    @abc.abstractmethod
    def _action_before_method(self, func_name):
        """Actions to be done before a method is executed. """
        pass

    @abc.abstractmethod
    def _action_after_method(self, func_name):
        """Actions to be done after a method is executed."""
        pass

    def wait(self, func):
        """Basic pause decorator.

        It permits running actions outside any function or method.
        """
        @wraps(func)
        def _inner(*args, **kwargs):
            """Inner function for passing argumnets."""
            name = func.__name__
            self._action_before_method(name)
            func(*args, **kwargs)
            self._action_after_method(name)
        return _inner


class EmptyDebugger(BaseDebugger):
    """Template class for null debugger.

    I created this empty class to avoid redundant verification of the debug
    flag. This way only one check is needed - see factory class Debugger.

    With an EmptyDebugger it is possible to have as many calls of debug
    functions as we want without the need to remove them when we don't want
    to use debug mode. The only thing we have to do in order to get that
    is set the debug flag to False.

    To avoid any possible errors any new public method form future debuggers
    should also be written here as an empty one.

    Also if you want to avoid deleting calls from other debuggers you can
    also inherit from this EmptyDebugger. This way any method that it's not
    mandatory and it's found around the code will be passed.
    """

    def __init__(self):
        """Empty __init__ method."""
        pass

    def pause(self, *args):
        """Empty pause method."""
        pass

    def _action_before_method(self, func_name):
        """Empty _action_before_method method."""
        pass

    def _action_after_method(self, func_name):
        """Empty _action_after_method method."""
        pass


class BasicDebugger(BaseDebugger):
    """BasicDebuger implementation.

    The only thing done by a basic debugger is pausing whenever we need it.
    """

    _PAUSE = 'pause'
    _RESUME = 'resume'

    def _new_client(self):
        """Creates a new client.

        This connects to the listener and until it's closed the program is in
        waiting state.
        """
        try:
            return connection.Client((self._ip, self._port),
                                     authkey=self._authkey)
        except connection.AuthenticationError:
            raise self._log.exception("AuthenticationError - Client creation"
                                      "failed. Check authentication key!")

    def _notice_server(self, client, action, msg):
        """Notify the server on what purpose we are connecting."""
        try:
            client.send_bytes(action)
            client.send_bytes(msg)
        except ValueError:
            self._log.exception("ValueError - Message has more than 32MB.")

    def pause(self, msg):
        """Interrupts the execution of the program.

        This function can be called to pause the execution at any given point
        in the program. Execution is resumed when the client recives "resume".
        """
        client = self._new_client()
        self._notice_server(client, self._PAUSE, msg)
        if client.recv_bytes() == self._RESUME:
            client.close()

    def _action_before_method(self, func_name):
        """Pauses before a method or function is executed."""
        self.pause("We are before method {}!".format(func_name))

    def _action_after_method(self, func_name):
        """Pauses after a method or function is executed."""
        self.pause("We are after method {}!".format(func_name))


class Debugger(object):
    """Factory debugger class.

    This is a class that decides which debugger should be used,
    based on the values provided in the config.
    """

    def __init__(self, config, log):
        """Initialize a factory object with several params.

        :config: Needed to establish the right debugger.
        :log: Passing the logging object.
        """
        self._config = config
        self._log = log

    def get(self):
        """Gets the right debugger."""
        if self._config.flag:
            with open(os.path.join('argus/debug/disclaimer.txt')) as f:
                self._log.warning(f.read())
            return BasicDebugger(self._config, self._log)
        else:
            return EmptyDebugger()
