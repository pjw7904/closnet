# Core libraries
import argparse


def parseArgs() -> argparse.Namespace:
    '''
    Read in the CLI arguments to build a folded-Clos Mininet.

    :returns: The inputted arguments.
    '''
    
    # ArgumentParser object to read in command-line arguments
    argParser = argparse.ArgumentParser(description="Network control protocol experimentation on folded-Clos Toplogies")

    # Protocol to install on the topology
    argParser.add_argument('protocol', 
                           choices=["mtp", "bgp"], 
                           help="The control protocol to install on the Mininet.")

    # Folded-Clos topology configuration
    argParser.add_argument("-t", "--tiers", 
                           type=int, 
                           metavar='numOfTiers', 
                           help="The number of tiers in the folded-Clos topology.")

    argParser.add_argument("-p", "--ports", 
                           type=int, 
                           metavar='numOfPorts', 
                           help="The number of ports each switch has in the folded-Clos topology.")
    
    argParser.add_argument("-s", "-southbound",
                            nargs=2, action='append', type=int, 
                            help='The number of links to a tier below by specficing the tier and the number of southbound ports per switch.')


    # Parse the arguments
    args = argParser.parse_args()

    return args


def validateTopology(config: argparse.Namespace) -> tuple:
    '''
    Validates the folded-Clos topology configuration inputted.

    :param args: The arguments to build a folded-Clos topology.
    :returns: A tuple containing the boolean result and a message
    '''

    # Check number of tiers
    if not (2 < config.tiers < 10):
        return (False, "Number of tiers configuration is invalid, (2-10 tiers supported)")
    
    # Check number of ports
    if not (4 <= config.ports <= 50 and config.ports % 2 == 0):
        return (False, "Number of ports configuration is invalid (4-50 ports supported)")

    return (True, "Configuration is valid")


def generateTestName(config: argparse.Namespace):
    '''
    Given a folded-Clos configuration, generate a test name for it
    that can be referenced later for repeated tests.
    
    :param args: The arguments to build a folded-Clos topology.
    :returns: The test name
    '''

    name = f"{config.protocol}_{config.tiers}_{config.ports}"

    #if(config.southbound):
    #    for tierKey, portValue in portModifications.items():
    #        name += f"_{tierKey}-{portValue}"

    return name
