from mininet.node import Node, Host
import subprocess

class BGPSwitch(Node):
    """
    A switch used to run the Border Gateway Protocol 4 (BGP-4) implementation
    provided by the Free Range Routing (FRR) control plane software
    for data center networks.
    """

    def __init__(self, name, **params):
        super(BGPSwitch, self).__init__(name, **params)
        self.processes = []  # List to keep track of daemon processes


    def start(self, controllers):
        print(f"Starting the BGP implementation on {self.name}")

        # Define the path to the FRR configuration file
        config_file = f"/tmp/{self.name}.conf"
        
        # Define the datacenter profile environment variable
        env = dict(FRR_PROFILE="datacenter")

        # Open a log file to capture the output of each daemon
        with open(f'./MTP-Mininet/logs/{self.name}.stdout', 'w') as log_file:
            # Start the Zebra daemon
            zebra_process = subprocess.Popen(
                ['/usr/lib/frr/zebra', '-f', config_file, '-d', '-z', f'/var/run/frr/{self.name}.zebra.api'],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env
            )
            self.processes.append(zebra_process)
            
            # Start the BGP daemon
            bgpd_process = subprocess.Popen(
                ['/usr/lib/frr/bgpd', '-f', config_file, '-d', '-z', f'/var/run/frr/{self.name}.bgpd.api'],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env
            )
            self.processes.append(bgpd_process)


    def stop(self):
        # Ensure all processes are terminated
        for process in self.processes:
            if process:
                process.terminate()
                process.wait()
        print(f"FRR daemons stopped on {self.name}")


    def config(self, **kwargs):
        # Call the base class config to do standard Mininet configuration
        super(BGPSwitch, self).config(**kwargs)
        # Start the FRR daemons once the node is configured
        self.start()


    def terminate(self):
        # Ensure all daemons are stopped when the node is terminated
        self.stop()
        super(BGPSwitch, self).terminate()


class BGPHost(Host):
    """
    A host that is used to connect to BGP switches for
    traffic generation testing. There is nothing
    special or BGP-specific about the host, it just
    gets it configured for tests.
    """

    def __init__(self, name, **params):
        super(BGPHost, self).__init__(name, **params)