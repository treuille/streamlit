# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base58
import copy
import json
import os
import uuid

from streamlit import config
from streamlit.ReportQueue import ReportQueue
from streamlit import util

from streamlit.logger import get_logger

LOGGER = get_logger(__name__)


class Report(object):
    """
    Contains parameters related to running a report, and also houses
    the two ReportQueues (master_queue and browser_queue) that are used
    to deliver messages to a connected browser, and to serialize the
    running report.
    """

    @classmethod
    def get_url(cls, host_ip):
        """Get the URL for any app served at the given host_ip.

        Parameters
        ----------
        host_ip : str
            The IP address of the machine that is running the Streamlit Server.

        Returns
        -------
        str
            The URL.
        """
        port = _get_browser_address_bar_port()
        return "http://%(host_ip)s:%(port)s" % {"host_ip": host_ip, "port": port}

    def __init__(self, script_path, argv):
        """Constructor.

        Parameters
        ----------
        script_path : str
            Path of the Python file from which this app is generated.

        argv : list of str
            Command-line arguments to run the script with.

        """
        basename = os.path.basename(script_path)

        self.script_path = os.path.abspath(script_path)
        self.script_folder = os.path.dirname(self.script_path)
        self.argv = argv
        self.name = os.path.splitext(basename)[0]

        # The master queue contains all messages that comprise the report.
        # If the user chooses to share a saved version of the report,
        # we serialize the contents of the master queue.
        self._master_queue = ReportQueue()

        # The browser queue contains messages that haven't yet been
        # delivered to the browser. Periodically, the server flushes
        # this queue and delivers its contents to the browser.
        self._browser_queue = ReportQueue()

        self.report_id = None
        self.generate_new_id()

    def get_debug(self):
        return {"master queue": self._master_queue.get_debug()}

    def parse_argv_from_command_line(self, cmd_line_str):
        """Parses an argv dict for this script from a command line string.

        Parameters
        ----------
        cmd_line_str : str
            The string to parse.

        Returns
        -------
        dict
            An argv dict, suitable for executing this Report with.

        """
        import shlex

        cmd_line_list = shlex.split(cmd_line_str)
        new_script_path = os.path.abspath(cmd_line_list[0])

        if new_script_path != self.script_path:
            raise ValueError(
                "Cannot change script from %s to %s"
                % (self.script_path, cmd_line_list[0])
            )

        self.argv = cmd_line_list

    def enqueue(self, msg):
        self._master_queue.enqueue(msg)
        self._browser_queue.enqueue(msg)

    def clear(self):
        # Master_queue retains its initial message; browser_queue is
        # completely cleared.
        initial_msg = self._master_queue.get_initial_msg()
        self._master_queue.clear()
        if initial_msg:
            self._master_queue.enqueue(initial_msg)

        self._browser_queue.clear()

    def flush_browser_queue(self):
        """Clears our browser queue and returns the messages it contained.

        The Server calls this periodically to deliver new messages
        to the browser connected to this report.

        This doesn't affect the master_queue.

        Returns
        -------
        list[ForwardMsg]
            The messages that were removed from the queue and should
            be delivered to the browser.

        """
        return self._browser_queue.flush()

    def generate_new_id(self):
        """Randomly generate an ID representing this report's execution."""
        # Convert to str for Python2
        self.report_id = str(base58.b58encode(uuid.uuid4().bytes).decode("utf-8"))

    def serialize_running_report_to_files(self):
        """Return a running report as an easily-serializable list of tuples.

        Returns
        -------
        list of tuples
            See `CloudStorage.save_report_files()` for schema. But as to the
            output of this method, it's just a manifest pointing to the Server
            so browsers who go to the shareable report URL can connect to it
            live.

        """
        LOGGER.debug("Serializing running report")

        manifest = self._build_manifest(
            status="running",
            external_server_ip=util.get_external_ip(),
            internal_server_ip=util.get_internal_ip(),
        )

        manifest_json = json.dumps(manifest).encode("utf-8")

        return [("reports/%s/manifest.json" % self.report_id, manifest_json)]

    def serialize_final_report_to_files(self):
        """Return the report as an easily-serializable list of tuples.

        Returns
        -------
        list of tuples
            See `CloudStorage.save_report_files()` for schema. But as to the
            output of this method, it's (1) a simple manifest and (2) a bunch
            of serialized ForwardMsgs.

        """
        LOGGER.debug("Serializing final report")

        messages = [
            copy.deepcopy(msg)
            for msg in self._master_queue
            if _should_save_report_msg(msg)
        ]

        first_delta_index = 0
        num_deltas = 0
        for idx in range(len(messages)):
            if messages[idx].HasField("delta"):
                messages[idx].metadata.delta_id = num_deltas
                if num_deltas == 0:
                    first_delta_index = idx
                num_deltas += 1

        manifest = self._build_manifest(
            status="done",
            num_messages=len(messages),
            first_delta_index=first_delta_index,
            num_deltas=num_deltas,
        )

        manifest_json = json.dumps(manifest).encode("utf-8")

        # Build a list of message tuples: (message_location, serialized_message)
        message_tuples = [
            (
                "reports/%(id)s/%(idx)s.pb" % {"id": self.report_id, "idx": msg_idx},
                msg.SerializeToString(),
            )
            for msg_idx, msg in enumerate(messages)
        ]

        manifest_tuples = [
            ("reports/%(id)s/manifest.json" % {"id": self.report_id}, manifest_json)
        ]

        # Manifest must be at the end, so clients don't connect and read the
        # manifest while the deltas haven't been saved yet.
        return message_tuples + manifest_tuples

    def _build_manifest(
        self,
        status,
        num_messages=None,
        first_delta_index=None,
        num_deltas=None,
        external_server_ip=None,
        internal_server_ip=None,
    ):
        """Build a manifest dict for this report.

        Parameters
        ----------
        status : 'done' or 'running'
            The report status. If the script is still executing, then the
            status should be RUNNING. Otherwise, DONE.
        num_messages : int or None
            Set only when status is DONE. The number of ForwardMsgs that this report
            is made of.
        first_delta_index : int or None
            Set only when status is DONE. The index of our first Delta message
        num_deltas : int or None
            Set only when status is DONE. The number of Delta messages in the report
        external_server_ip : str or None
            Only when status is RUNNING. The IP of the Server's websocket.
        internal_server_ip : str or None
            Only when status is RUNNING. The IP of the Server's websocket.

        Returns
        -------
        dict
            The actual manifest. Schema:
            - localId: str,
            - numMessages: int or None,
            - firstDeltaIndex: int or None,
            - numDeltas: int or None,
            - serverStatus: 'running' or 'done',
            - externalServerIP: str or None,
            - internalServerIP: str or None,
            - serverPort: int

        """
        if status == "running":
            configured_server_address = config.get_option("browser.serverAddress")
        else:
            configured_server_address = None

        return dict(
            name=self.name,
            numMessages=num_messages,
            firstDeltaIndex=first_delta_index,
            numDeltas=num_deltas,
            serverStatus=status,
            configuredServerAddress=configured_server_address,
            externalServerIP=external_server_ip,
            internalServerIP=internal_server_ip,
            # Don't use _get_browser_address_bar_port() here, since we want the
            # websocket port, not the web server port. (These are the same in
            # prod, but different in dev)
            serverPort=config.get_option("browser.serverPort"),
        )


def _should_save_report_msg(msg):
    """Returns True if the given ForwardMsg should be serialized into
    a shared report.

    We serialize report & session metadata and deltas, but not transient
    events such as upload progress.

    """

    msg_type = msg.WhichOneof("type")

    # Strip out empty delta messages. These don't have any data in them
    # by definition, so omitting them can save the user from a potentially
    # long load time with no downside.
    if (
        msg_type == "delta"
        and msg.delta.WhichOneof("type") == "new_element"
        and msg.delta.new_element.WhichOneof("type") == "empty"
    ):
        return False

    return msg_type == "initialize" or msg_type == "new_report" or msg_type == "delta"


def _get_browser_address_bar_port():
    """Get the report URL that will be shown in the browser's address bar.

    That is, this is the port where static assets will be served from. In dev,
    this is different from the URL that will be used to connect to the
    server-browser websocket.

    """
    if config.get_option("global.developmentMode") and config.get_option(
        "global.useNode"
    ):
        return 3000
    return config.get_option("browser.serverPort")
