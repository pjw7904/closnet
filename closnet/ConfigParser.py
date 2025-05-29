# Core libraries
import argparse
import json
import sys


def parseArgs() -> argparse.Namespace:
    '''
    Read in the CLI arguments to build a folded-Clos Mininet.
    A JSON configuration file with the same arguments can be provided as well, the function can read from both.
    
    :returns: The inputted arguments.
    '''

    # First parser: just for --file so we can detect it without requiring other args
    configFileParser = argparse.ArgumentParser(add_help=False)
    configFileParser.add_argument("-f", "--file",
                           type=str, 
                           help="Path to a JSON config file.", 
                           default=None)

    # Parse known args first (so it won't fail if the protocol arg is missing)
    prelimArgs, remaining_argv = configFileParser.parse_known_args()

    # Second parser: standard ArgumentParser object to read in command-line arguments
    argParser = argparse.ArgumentParser(description="Network control protocol experimentation on folded-Clos Toplogies")

    # Protocol to install on the topology
    argParser.add_argument('protocol', 
                           choices=["mtp", "bgp"],
                           nargs='?',
                           help="The control protocol to install on the Mininet.")

    # Folded-Clos topology configuration
    # Include --file here too so it shows up in --help, etc.
    argParser.add_argument("-f", "--file", 
                           type=str, 
                           help="Path to a JSON config file.", 
                           default=None)

    argParser.add_argument("-t", "--tiers", 
                           type=int, 
                           metavar='numOfTiers', 
                           help="The number of tiers in the folded-Clos topology.")

    argParser.add_argument("-p", "--ports", 
                           type=int, 
                           metavar='numOfPorts', 
                           help="The number of ports each switch has in the folded-Clos topology.")
    
    argParser.add_argument("-s", "--southbound",
                            nargs=2, action='append', type=int, 
                            help='The number of links to a tier below by specficing the tier and the number of southbound ports per switch.')

    # Additional utilities/features configuration
    argParser.add_argument('--visualize', 
                           action='store_true')
    
    argParser.add_argument('--bfd', 
                           action='store_true',
                           help="Start the FRR BFD daemon (bfdd) on every BGP switch")
    
    # If a JSON config was passed in via the preliminary parse, load it and set those values as defaults.
    if prelimArgs.file:
        try:
            with open(prelimArgs.file, "r") as f:
                config_data = json.load(f)

            # Set JSON values as defaults.
            argParser.set_defaults(**config_data)

        except FileNotFoundError:
            sys.exit(f"Error: The file '{prelimArgs.file}' was not found.")

    # Now parse again (fully), so that CLI overrides JSON if both are specified.
    args = argParser.parse_args(remaining_argv)

    # Ensure that the file argument is included in the final args.
    if args.file is None:
        args.file = prelimArgs.file

    return args


def validateTopology(config: argparse.Namespace) -> tuple:
    '''
    Validates the folded-Clos topology configuration inputted.

    :param args: The arguments to build a folded-Clos topology.
    :returns: A tuple containing the boolean result and a message
    '''

    # Check number of tiers
    if not (2 <= config.tiers <= 10):
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

    if(config.southbound):
        for portCountChange in config.southbound:
            tier = portCountChange[0]
            portCount = portCountChange[1]
            name += f"_{tier}-{portCount}"

    return name
