# Put the script in the root of the project to access Closnet
import os
import sys
parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.append(parent_dir)

from closnet.protocols.bgp.analysis.BGPAnalysis import BGPAnalysis
from closnet.experiment.Experiment import runExperimentAnalysis

# Put the absolute path here to the log directory
LOG_DIR = "/home/pjw7904/closnet/logs/bgp/bad_bgp_logging"

exp = BGPAnalysis(LOG_DIR)
runExperimentAnalysis(LOG_DIR, exp, debugging=True)
print("Done - results.log written beside your nodes/ folder")
