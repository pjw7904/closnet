'''
author: Peter Willis (pjw7904@rit.edu)

Testing out the custom topology and switch (found in protocols --> test).
'''

# Mininet libraries
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI

# Custom libraries
from closnet.protocols.test.mininet_switch.BasicCustomSwitch import TestSwitch, CCodeSwitch
from closnet.topo_definitions.GraphmlTopo import GraphmlTopo

def logTest():
    '''
    Running a Mininet experiment with a custom topolology and Switch.
    '''

    # Define the topology type
    testTopology = GraphmlTopo("../topologies/graphml/triangle.graphml")

    # Define the network, use the TEST SWTICH
    net = Mininet(topo=testTopology, 
                  switch=TestSwitch, 
                  controller=None)

    # Run the experiment
    net.start()
    CLI(net)
    net.stop()
    
    return

def CCodeTest():
    '''
    Running a Mininet experiment with custom C code switches.
    '''

    # Define the topology type
    testTopology = GraphmlTopo("topologies/graphml/host_test.graphml", "h")

    # Define the network, use the C CODE SWITCH
    net = Mininet(topo=testTopology, 
                  switch=CCodeSwitch,
                  controller=None)

    # Run the experiment
    net.start()
    CLI(net)
    net.stop()
    
    return


if __name__ == '__main__':
    setLogLevel('info')
    CCodeTest()