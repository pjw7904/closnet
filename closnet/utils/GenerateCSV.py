import re
import csv
import sys
from pathlib import Path
from typing import Optional, Tuple

# === Regex patterns for results.log ===
TS     = re.compile(r"Experiment start time:\s+(\d+)")
INTF   = re.compile(r"Interface failure time:\s+(\d+)")
STOP   = re.compile(r"Experiment stop timestamp:\s+(\d+)")
CONV   = re.compile(r"Convergence time:\s+(\d+)")
BLAST  = re.compile(r"([\d.]+)% of nodes received")
OVER   = re.compile(r"=== OVERHEAD ===\s+(\d+)\s+bytes", re.S)
TRAFFC = re.compile(r"=== TRAFFIC ===\s+(.*)", re.S)

# === Regex patterns for experiment.log ===
FAIL_NODE   = re.compile(r"Failed node:\s+(\S+)")
FAIL_NEIGH  = re.compile(r"Failed neighbor:\s+(\S+)")
# Accept either "Failure Type:" or "Experiment type:" (case‑insensitive)
FAIL_TYPE   = re.compile(r"(?:Failure|Experiment)\s+type:\s+(.+)", re.I)


def parse(exp_dir: Path) -> Optional[Tuple]:
    """
    Parse *results.log* and *experiment.log* inside a single experiment directory.

    Returns a tuple in the following order (matches the CSV header):
        start_time, intf_failure_time, stop_time,
        failed_node, failed_neighbor, failure_type,
        convergence_ms, blast_radius_pct, overhead_bytes, traffic_summary

    If either file is malformed, returns ``None``.
    """
    res_path = exp_dir / "results.log"
    exp_path = exp_dir / "experiment.log"

    # Both files are needed; skip if results.log missing
    if not res_path.exists():
        sys.stderr.write(f"[WARN] {res_path} not found – skipping\n")
        return None

    try:
        res_txt = res_path.read_text()
        exp_txt = exp_path.read_text() if exp_path.exists() else ""

        start_ts  = int(TS.search(res_txt).group(1))
        intf_ts   = int(INTF.search(res_txt).group(1))
        stop_ts   = int(STOP.search(res_txt).group(1))

        failed_node  = FAIL_NODE.search(exp_txt).group(1) if FAIL_NODE.search(exp_txt) else "Unknown"
        failed_neigh = FAIL_NEIGH.search(exp_txt).group(1) if FAIL_NEIGH.search(exp_txt) else "Unknown"

        # Normalize failure type to just "hard" / "soft" if possible
        ftype_match = FAIL_TYPE.search(exp_txt)
        if ftype_match:
            ftype_raw = ftype_match.group(1).strip().lower()
            failure_type = (
                "hard" if ftype_raw.startswith("hard")
                else "soft" if ftype_raw.startswith("soft")
                else ftype_raw
            )
        else:
            failure_type = "unknown"

        convergence_ms = int(CONV.search(res_txt).group(1))
        blast_pct      = float(BLAST.search(res_txt).group(1))
        overhead_bytes = int(OVER.search(res_txt).group(1))
        traffic        = TRAFFC.search(res_txt).group(1).strip() if TRAFFC.search(res_txt) else "None"

        return (
            start_ts, intf_ts, stop_ts,
            failed_node, failed_neigh, failure_type,
            convergence_ms, blast_pct, overhead_bytes, traffic,
        )
    except (AttributeError, ValueError) as e:
        sys.stderr.write(f"[WARN] Malformed logs in {exp_dir}: {e}\n")
        return None


def run(protocol: str, topo: str) -> None:
    """Aggregate experiment metrics for *topo* under *logs/<protocol>*."""
    root = Path("logs") / protocol
    rows = []

    # Each experiment directory is of the form <topologyName>_<timestamp>/
    for exp_dir in sorted(root.glob(f"{topo}_*/")):
        tup = parse(exp_dir)
        if tup:
            rows.append(tup)

    if not rows:
        sys.exit("No matching experiments found.")

    out = root / f"{topo}_aggregate_results.csv"
    hdr = [
        "experiment_start_time",
        "interface_failure_time",
        "experiment_stop_time",
        "failed_node",
        "failed_neighbor",
        "failure_type",
        "convergence_time_ms",
        "blast_radius_percent",
        "overhead_bytes",
        "traffic_result",
    ]

    with out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(hdr)
        writer.writerows(rows)

    out.chmod(0o777)
    print(f"Wrote {len(rows)} rows → {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: generate_csv.py <protocol> <topology>")
    run(sys.argv[1], sys.argv[2])
