'''
author: Peter Willis (pjw7904@rit.edu)

Used to test the functionality of creating a custom subclass switch from the Switch superclass.

Don't use this switch for any real experiments, it's just to learn and play around with.
'''

from mininet.node import Switch
from mininet.log import info

class TestSwitch(Switch):
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