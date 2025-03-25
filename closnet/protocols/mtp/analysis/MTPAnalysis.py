# Core libraries
import re
import logging

# Custom libraries
from closnet.experiment.ExperimentAnalysis import ExperimentAnalysis

class MTPAnalysis(ExperimentAnalysis):
    """
    MTPAnalysis is analogous to BGPAnalysis, but adapted to parse MTP logs.
    We look for:

    1) An interface failure line on the failing node:
       "Detected a failure, shut down port L_1-eth1 at time 1742490729154"

    2) A failure update line on other nodes:
       "FAILURE UPDATE message received at 1742490729396, on port L_3-eth1"
       followed (possibly on next line) by:
       "Message size = 20"

    3) A neighbor's keep-alive line:
       "--------Disabled for port T_1-eth1 due to a missing KEEP ALIVE at time 1742490729396--------"

    Many lines don't contain timestamps at all; we ignore those.
    """

    # Example regex patterns:
    #  We parse a 13-digit timestamp from "at 1742490729396".
    RE_INTERFACE_FAILURE = re.compile(r'Detected a failure, shut down port ([^ ]+) at time (\d{13})')
    RE_FAILURE_UPDATE = re.compile(r'FAILURE UPDATE message received at (\d{13}), on port ([^ ]+)')
    RE_KEEPALIVE_DISABLED = re.compile(r'Disabled for port ([^ ]+) due to a missing KEEP ALIVE at time (\d{13})')
    RE_MESSAGE_SIZE = re.compile(r'Message size\s*=\s*(\d+)')


    def __init__(self, experimentDirPath):
        super().__init__(experimentDirPath)
        # MTP lines show the timestamp in the text itself, e.g. "... at time 1742490729154" so no self.timestamp_format needed.


    def parseLogFile(self, nodeName, logFile):
        convergenceTime = 0
        overhead = 0
        updated = False # Used for blast radius calculation. Nodes that are not updated are not part of the blast radius.

        with open(logFile) as file:
            for line in file:
                line = line.strip()

                # 1) Check for "Detected a failure..." line on the failing node.
                matchFail = self.RE_INTERFACE_FAILURE.search(line)
                if matchFail:
                    portName = matchFail.group(1)
                    recordTS = int(matchFail.group(2))

                    # Make sure this timestamp is within the experiment window:
                    if not self.isValidLogRecord(recordTS, useExperimentStartTime=True):
                        continue

                    # If this belongs to the node that we expected to fail,
                    # record the interface failure time. That pins the “start” of reconvergence.
                    if self.isFailedNode(nodeName) and self.isFailedInterface(portName):
                        # Record the time the interface actually failed
                        self.intf_failure_time = recordTS

                        convergenceTime = max(convergenceTime, recordTS)
                        updated = True  # The failed node definitely "knows" something changed
                        logging.debug(f"[{nodeName}] Found local interface failure on {portName} @ {recordTS}")

                    # Or if this belongs to the neighbor node failing an interface
                    elif self.isFailedNeighbor(nodeName) and self.isFailedNeighborInterface(portName):
                        # For BGP we sometimes track a second interface failure time, or
                        # treat it as a separate “failure” marker. Up to you.
                        # But you might mark it as updated, too.
                        convergenceTime = max(convergenceTime, recordTS)
                        updated = True
                        logging.debug(f"[{nodeName}] Found neighbor interface failure on {portName} @ {recordTS}")

                    else:
                        # This might be some unexpected failure line for some other port or node
                        logging.debug(f"[{nodeName}] Saw unexpected failure line: {line}")

                    continue # move onto next log.

                # 2) Check for “FAILURE UPDATE message received at 1742490729396...”
                matchUpdate = self.RE_FAILURE_UPDATE.search(line)
                if matchUpdate:
                    recordTS = int(matchUpdate.group(1))

                    if not self.isValidLogRecord(recordTS):
                        continue

                    # That means the node got a failure update => mark updated
                    convergenceTime = max(convergenceTime, recordTS)
                    updated = True

                    logging.debug(f"[{nodeName}] Saw FAILURE UPDATE line: {line}")

                    # The next line typically might have a "Message size = X"
                    # but we can’t guarantee it’s the immediate next line if logs are messy.
                    # So let's just keep reading lines until we see "Message size =".
                    # Often you can keep it simpler: just parse overhead in the same loop if consistent.
                    continue

                # 3) Check for “Disabled for port... missing KEEP ALIVE...”
                matchKA = self.RE_KEEPALIVE_DISABLED.search(line)
                if matchKA:
                    portName  = matchKA.group(1)
                    recordTS  = int(matchKA.group(2))

                    if not self.isValidLogRecord(recordTS):
                        continue

                    # A missing keep-alive is effectively a sign that this node
                    # "noticed" a failure => that’s a reconvergence event
                    convergenceTime = max(convergenceTime, recordTS)
                    updated = True
                    logging.debug(f"[{nodeName}] KEEP ALIVE failure for {portName} @ {recordTS}")

                    continue

                # 4) Possibly parse overhead from "Message size = XX"
                matchSize = self.RE_MESSAGE_SIZE.search(line)
                if matchSize:
                    sizeVal = int(matchSize.group(1))

                    # If the line has no timestamp, we could either
                    #   (a) skip it, or
                    #   (b) assume it shares a timestamp with a preceding “FAILURE UPDATE” line
                    # For simplicity, we can skip if no recognized TS is in the line:
                    # or keep a "lastRecordTS" from a prior matched line, etc.
                    # Below we do a skip if no prior match gave a valid TS:

                    # In some protocols you might just add overhead any time we see "Message size = X"
                    # because presumably it’s within the same timeslice as the last recognized event:
                    overhead += sizeVal
                    logging.debug(f"[{nodeName}] +{sizeVal} overhead => total {overhead}")

                    continue

                # For lines with no relevant patterns, do nothing.

        # Return the largest event timestamp (convergenceTime), updated boolean, overhead bytes
        logging.debug(f"[{nodeName}] Final: convTime={convergenceTime}, updated={updated}, overhead={overhead}")
        return convergenceTime, updated, overhead
