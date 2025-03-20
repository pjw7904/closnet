from mininet.node import Node, Host

class BGPSwitch(Node):
    """
    A switch used to run the Border Gateway Protocol 4 (BGP-4) implementation
    provided by the Free Range Routing (FRR) control plane software
    for data center networks.
    """

    ID = 0

    def __init__(self, name, **kwargs):
        kwargs['inNamespace'] = True
        super(BGPSwitch, self).__init__(name, **kwargs)

        BGPSwitch.ID += 1
        self.switch_id = BGPSwitch.ID

    def start(self, controllers):
        # Turn on the loopback interface
        self.cmd('ifconfig lo up')
        self.waitOutput()

        # Enable IPv4 forwarding
        self.cmd("sysctl -w net.ipv4.ip_forward=1")
        self.waitOutput()

        # Define the path to the FRR configuration file
        config_file = f"/tmp/{self.name}.conf"

        # Start Zebra in the node's namespace
        start_zebra = (
            f'/usr/lib/frr/zebra '
            f'-d '
            f'-N {self.name} '
            f'-i /tmp/{self.name}.zebra.pid'
        )
        self.cmd(start_zebra)
        self.waitOutput()

        # Start BGP in the node's namespace
        start_bgpd = (
            f'/usr/lib/frr/bgpd '
            f'-d '
            f'-N {self.name} '
            f'-i /tmp/{self.name}.bgpd.pid'
        )
        self.cmd(start_bgpd)
        self.waitOutput()

        # Load the config via vtysh
        self.cmd(f'vtysh -N "{self.name}" -f "{config_file}"')
        self.waitOutput()

        print(f"FRR daemons (zebra & bgpd) started on {self.name}")

    def stop(self):
        """Stops FRR daemons running on this node."""

        # List of daemons to stop
        DAEMONS = ('zebra', 'bgpd')

        # Terminate daemons using PIDs from PID files
        for daemon in DAEMONS:
            pid_file = f"/tmp/{self.name}.{daemon}.pid"

            if self.cmd(f'test -f {pid_file} && echo "exists"').strip() == 'exists':
                pid = self.cmd(f'cat {pid_file}').strip()

                try:
                    # Kill the process inside the node's namespace
                    self.cmd(f'kill {pid}')
                    print(f"Terminated {daemon} for {self.name} (PID {pid})")

                except Exception as e:
                    print(f"Failed to terminate {daemon} for {self.name}: {e}")

                # Remove the PID file
                self.cmd(f'rm -f {pid_file}')

            else:
                print(f"PID file not found: {pid_file}")

        # Clean up any remaining files related to this node (not used currently, but if needed in the future)
        #self.cmd(f'rm -f /tmp/{self.name}.*')

        print(f"FRR daemons stopped on {self.name}\n")


    def config(self, **kwargs):
        # Call the base class config to do standard Mininet configuration
        super(BGPSwitch, self).config(**kwargs)

        # Start the FRR daemons once the node is configured
        self.start()


    def terminate(self):
        # Ensure all daemons are stopped when the node is terminated
        #self.stop() --> this calls it twice when Mininet exit is called, but keeping just in case
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
