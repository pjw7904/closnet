#!/usr/bin/env bash
# run_experiments.sh  ─ run experiment.json N times, then aggregate

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <number_of_runs>"
  exit 1
fi

RUNS=$1

for ((i = 1; i <= RUNS; i++)); do
  echo -e "\n=== RUN $i/$RUNS ==="
  sudo python3 -m closnet --file test.json
done

# Create the CSV from all runs of this topology/protocol
sudo python3 -m closnet --file test.json --csv
