from mininet.node import Node, Host
import subprocess

class MTPSwitch(Node):
    """
    A switch used to run the Meshed Tree Protocol (MTP) implementation
    for data center networks.
    """

    def __init__(self, name, **params):
        params['inNamespace'] = True
        super(MTPSwitch, self).__init__(name, **params)
        self.process = None


    def start(self, controllers):
        log_file = open(f'/tmp/{self.name}.stdout', 'w', buffering=1)

        # *** use self.popen so mnexec puts it inside the netns ***
        self.process = self.popen(
            ['./closnet/protocols/mtp/bin/mtp', self.name, '/tmp'],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        print(f"MTP started on {self.name}")


    def stop(self):
        # Ensure the process is terminated
        if self.process:
            self.process.terminate()
            self.process.wait()
            print(f"MTP stopped on {self.name}\n")


class MTPHost(Host):
    """
    A host that is used to connect to MTP switches for
    traffic generation testing. There is nothing
    special or MTP-specific about the host, it just
    gets it configured for tests.
    """

    def __init__(self, name, **params):
        super(MTPHost, self).__init__(name, **params)
