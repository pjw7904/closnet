from mininet.node import Node, Host
import subprocess

class MTPSwitch(Node):
    """
    A switch used to run the Meshed Tree Protocol (MTP) implementation
    for data center networks.
    """

    def __init__(self, name, **params):
        super(MTPSwitch, self).__init__(name, **params)
        self.process = None


    def start(self, controllers):
        # Open the log file in write mode
        with open(f'/tmp/{self.name}.stdout', 'w') as log_file:
            # Start the process (look into popen() function of node)
            # Start the C program in the background
            self.process = subprocess.Popen(
                ['./closnet/protocols/mtp/bin/mtp', self.name, "/tmp"],
                stdout=log_file,
                stderr=subprocess.STDOUT)
        
        print(f"MTP started on {self.name}")


    def stop(self):
        # Ensure the process is terminated
        if self.process:
            self.process.terminate()
            self.process.wait()
            print(f"MTP stopped on {self.name}\n")


    def attach(self, intf):
        "Connect a data port"
        assert(0)


    def detach(self, intf):
        "Disconnect a data port"
        assert(0)


class MTPHost(Host):
    """
    A host that is used to connect to MTP switches for
    traffic generation testing. There is nothing
    special or MTP-specific about the host, it just
    gets it configured for tests.
    """

    def __init__(self, name, **params):
        super(MTPHost, self).__init__(name, **params)
