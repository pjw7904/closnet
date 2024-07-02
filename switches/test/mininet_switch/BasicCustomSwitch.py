'''
author: Peter Willis (pjw7904@rit.edu)

Used to test the functionality of creating a custom subclass switch from the Switch superclass.

Don't use this switch for any real experiments, it's just to learn and play around with.
'''

from mininet.node import Switch
from mininet.node import Node
from mininet.log import info
import subprocess

class TestSwitch(Switch):
    """
    A test switch (extending the Switch class) used to simply print that it works.
    As basic as it gets for a custom switch.
    """

    def __init__(self, name, **kwargs):
        '''
        Constructor for Testing switch.
        This calls the superclass Switch init and doesn't modify anything.
        '''

        # Call the superclass Switch constructor with name and the keyword argument.
        Switch.__init__(self, name, **kwargs)

    def start(self, controllers):
        '''
        Startup procedure for test switch.
        Ignore controllers, we won't use it, but it's a positional argument in the Switch class.
        '''

        info(f"{self.name} is starting up.\n")

        logFile = open(f"{self.name}.log", "w")
        logFile.write("If you see this, yay!")
        logFile.close()

    def attach(self, intf):
        "Connect a data port"
        assert(0)

    def detach(self, intf):
        "Disconnect a data port"
        assert(0)


class CCodeSwitch(Node):
    """
    A test switch (extending the Node class) used to test running C code.
    """

    def __init__(self, name, **params):
        super(CCodeSwitch, self).__init__(name, **params)
        self.process = None

    def start(self, controllers):
        # Start the C program in the background
        print(f"Starting CCodeSwitch {self.name}")

        # Open the log file in write mode
        with open('test.log', 'w') as log_file:
            # Start the process
            self.process = subprocess.Popen(
                ['/home/pjw7904/MTP-Mininet/switches/test/bin/switch_logic_print', self.name],
                stdout=log_file,
                stderr=subprocess.STDOUT)


    def stop(self):
        # Ensure the process is terminated
        if self.process:
            self.process.terminate()
            self.process.wait()
            print(f"CCodeSwitch {self.name} stopped")

    def attach(self, intf):
        "Connect a data port"
        assert(0)

    def detach(self, intf):
        "Disconnect a data port"
        assert(0)
