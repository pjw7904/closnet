import re, csv, sys
from pathlib import Path
from typing import Optional, Tuple

TS     = re.compile(r"Experiment start time:\s+(\d+)")
INTF   = re.compile(r"Interface failure time:\s+(\d+)")
STOP   = re.compile(r"Experiment stop timestamp:\s+(\d+)")
CONV   = re.compile(r"Convergence time:\s+(\d+)")
BLAST  = re.compile(r"([\d.]+)% of nodes received")
OVER   = re.compile(r"=== OVERHEAD ===\s+(\d+)\s+bytes", re.S)
TRAFFC = re.compile(r"=== TRAFFIC ===\s+(.*)", re.S)

def parse(path: Path) -> Optional[Tuple]:
    txt = path.read_text()
    try:
        return (
            int(TS.search(txt).group(1)),
            int(INTF.search(txt).group(1)),
            int(STOP.search(txt).group(1)),
            int(CONV.search(txt).group(1)),
            float(BLAST.search(txt).group(1)),
            int(OVER.search(txt).group(1)),
            TRAFFC.search(txt).group(1).strip() if TRAFFC.search(txt) else "None",
        )
    except AttributeError:
        sys.stderr.write(f"[WARN] Malformed {path}\n")
        return None

def run(protocol: str, topo: str) -> None:
    root  = Path("logs") / protocol
    rows  = []
    for d in sorted(root.glob(f"{topo}_*/")):
        res = d / "results.log"
        if res.exists():
            tup = parse(res)
            if tup:
                rows.append(tup)
    if not rows:
        sys.exit("No matching experiments found.")
    out  = root / f"{topo}_aggregate_results.csv"
    hdr  = ["experiment_start_time","interface_failure_time","experiment_stop_time",
            "convergence_time_ms","blast_radius_percent","overhead_bytes","traffic_result"]
    with out.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(hdr); w.writerows(rows)
    out.chmod(0o777)
    print(f"Wrote {len(rows)} rows → {out}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: generate_csv.py <protocol> <topology>")
    run(sys.argv[1], sys.argv[2])
