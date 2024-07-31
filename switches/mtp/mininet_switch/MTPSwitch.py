from mininet.node import Switch
from mininet.node import Node
from mininet.log import info
import subprocess
import os

class MTPSwitch(Node):
    """
    A switch used to run the Meshed Tree Protocol (MTP) implementation
    for data center networks.
    """

    def __init__(self, name, **params):
        super(MTPSwitch, self).__init__(name, **params)
        self.process = None


    def start(self, controllers):
        # Start the C program in the background
        print(f"Starting the MTP implementation on {self.name}")

        # Open the log file in write mode
        with open(f'./MTP-Mininet/logs/{self.name}.log', 'w') as log_file:
            # Start the process
            self.process = subprocess.Popen(
                ['./MTP-Mininet/switches/mtp/bin/mtp', self.name, "/tmp"],
                stdout=log_file,
                stderr=subprocess.STDOUT)


    def stop(self):
        # Ensure the process is terminated
        if self.process:
            self.process.terminate()
            self.process.wait()
            print(f"{self.name} has stopped")


    def attach(self, intf):
        "Connect a data port"
        assert(0)


    def detach(self, intf):
        "Disconnect a data port"
        assert(0)
