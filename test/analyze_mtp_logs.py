# Put the script in the root of the project to access Closnet
import os
import sys
parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.append(parent_dir)

from closnet.protocols.mtp.analysis.MTPAnalysis import MTPAnalysis
from closnet.experiment.Experiment import runExperimentAnalysis

# Put the absolute path here to the log directory
LOG_DIR = "/home/pjw7904/closnet/logs/mtp/mtp_3_4_1-1_soft_1751044442418"

exp = MTPAnalysis(LOG_DIR)
runExperimentAnalysis(LOG_DIR, exp, debugging=True)
print("Done - results.log written beside your nodes/ folder")
