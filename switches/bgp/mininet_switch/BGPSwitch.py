from mininet.node import Switch, Node, Host
import subprocess

class BGPSwitch(Switch):
    """
    A switch used to run the Border Gateway Protocol 4 (BGP-4) implementation
    provided by the Free Range Routing (FRR) control plane software
    for data center networks.
    """

    def __init__(self, name, **kwargs):
        kwargs['inNamespace'] = True
        super(BGPSwitch, self).__init__(name, **kwargs)
        self.processes = []  # List to keep track of daemon processes


    def start(self, controllers):
        print(f"Starting the BGP implementation on {self.name}")

        # Define the path to the FRR configuration file
        config_file = f"/tmp/{self.name}.conf"
        
        # Define the datacenter profile environment variable
        env = 'FRR_PROFILE="datacenter"'

        # Start Zebra in the node's namespace
        zebra_cmd = (
            f'{env} /usr/lib/frr/zebra '
            f'-f {config_file} '
            f'-d '
            f'-z /var/run/frr/{self.name}.zebra.api '
            f'-i /var/run/frr/{self.name}.zebra.pid'
        )
        self.cmd(zebra_cmd)

        # Start BGP in the node's namespace
        bgpd_cmd = (
            f'{env} /usr/lib/frr/bgpd '
            f'-f {config_file} '
            f'-d '
            f'-z /var/run/frr/{self.name}.bgpd.api '
            f'-i /var/run/frr/{self.name}.bgpd.pid'
        )
        self.cmd(bgpd_cmd)

        print(f"FRR daemons started on {self.name}")

    def stop(self):
        # Ensure all processes are terminated using pkill
        import os

        # Try to gracefully terminate the managed processes first
        for process in self.processes:
            if process:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # If the process didn't terminate, force kill
                    process.kill()

        # Now, use pkill to ensure all zebra and bgpd processes for this node are killed
        os.system(f"sudo pkill -f '/usr/lib/frr/zebra -f /tmp/{self.name}.conf'")
        os.system(f"sudo pkill -f '/usr/lib/frr/bgpd -f /tmp/{self.name}.conf'")

        # Clean up PID files after ensuring the processes are terminated
        pid_files = [
            f"/var/run/frr/{self.name}.zebra.pid",
            f"/var/run/frr/{self.name}.bgpd.pid"
        ]

        for pid_file in pid_files:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                print(f"Removed PID file: {pid_file}")

        self.processes = []  # Clear the list of processes after stopping
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
