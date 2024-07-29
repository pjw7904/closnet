from mako.template import Template
import os

def generateConfigMTP(topology):
    '''
    Create and save configuration files for MTP nodes.

    :param topology: The NetworkX-formatted topology.
    '''

    TEMPLATE_LOCATION = os.path.join(os.path.dirname(__file__), 
                                     "switches/mtp/config_template/mtp_conf.mako")
    CONFIG_DIR = "/tmp"
    COMPUTE_TIER = 0 # We do not want config files for the compute nodes.

    # Open the MTP configuration template
    try: 
        mtpTemplate = Template(filename=TEMPLATE_LOCATION)
    except Exception as e:
        print(f"Exception: {e}")

    # Iterate through the nodes in the topology
    for node in topology:
        tier = topology.nodes[node]['tier']

        # Only configure MTP devices, not compute devices.
        if(tier > COMPUTE_TIER):
            # Grab configuration data
            nodeTemplate = {'tier': tier, 
                            'isTopSpine': topology.nodes[node]['isTopTier']}

            # Process the data and render a custom MTP configuration.
            mtpConfig = mtpTemplate.render(**nodeTemplate)

            # Save the configuration in the file <node_name>.conf
            with open(os.path.join(CONFIG_DIR, f"{node}.conf"), 'w') as configFile:
                configFile.write(mtpConfig)

    return
