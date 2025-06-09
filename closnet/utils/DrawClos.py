# External Libraries
import networkx as nx
import matplotlib.pyplot as plt
from copy import deepcopy
from collections import defaultdict, deque
from typing import Optional, Tuple

__all__ = ["drawFoldedClos"]

# ---------------------------------------------------------------------------
# Helper – build a *directed* view of the folded‑Clos so we can reason about
#           north‑ and south‑bound traversal for valley‑free routing.
# ---------------------------------------------------------------------------

def _build_directed(topology: nx.Graph) -> nx.DiGraph:
    """Return a directed overlay with `direction` attributes (north/south).

    Any edge lacking *northbound* / *southbound* metadata on its endpoints is
    tagged "unknown" so it will be ignored by the valley‑free checker.
    """
    G = nx.DiGraph()
    for n, data in topology.nodes(data=True):
        G.add_node(n, **data)

    for u, v in topology.edges():
        dir_uv = "north" if v in topology.nodes[u].get("northbound", []) else (
            "south" if v in topology.nodes[u].get("southbound", []) else "unknown")
        dir_vu = "north" if u in topology.nodes[v].get("northbound", []) else (
            "south" if u in topology.nodes[v].get("southbound", []) else "unknown")
        G.add_edge(u, v, direction=dir_uv)
        G.add_edge(v, u, direction=dir_vu)
    return G

# ---------------------------------------------------------------------------
# Valley‑free reachability check (north‑only, or north‑then‑south)
# ---------------------------------------------------------------------------

def _has_valley_free(G: nx.DiGraph, src: str, dst: str) -> bool:
    if src == dst:
        return True
    q = deque([(src, "start")])  # (node, phase)
    seen = set()
    while q:
        node, phase = q.popleft()
        if (node, phase) in seen:
            continue
        seen.add((node, phase))
        for nbr in G.neighbors(node):
            direction = G.edges[node, nbr]["direction"]
            if direction == "unknown":
                continue
            if phase == "start":
                next_phase = "down" if direction == "south" else "up"
            elif phase == "up":
                if direction == "north":
                    next_phase = "up"
                elif direction == "south":
                    next_phase = "down"
                else:
                    continue
            else:  # phase == down
                if direction != "south":
                    continue
                next_phase = "down"

            if nbr == dst:
                return True
            q.append((nbr, next_phase))
    return False

# ---------------------------------------------------------------------------
# Compute‑reachability classification
# ---------------------------------------------------------------------------

def _classify_nodes(G: nx.DiGraph) -> dict[str, bool]:
    """Return a map of node → *True* if it can reach *every* compute node."""
    compute_nodes = [n for n, d in G.nodes(data=True)
                     if d.get("tier", 999) == 0 or str(n).startswith("C")]
    status = {n: True for n in G.nodes}
    for src in G.nodes:
        for dst in compute_nodes:
            if src == dst:
                continue
            if not _has_valley_free(G, src, dst):
                status[src] = False
                break
    return status

# ---------------------------------------------------------------------------
# Deterministic tier layout
# ---------------------------------------------------------------------------

def _tier_layout(topology: nx.Graph, y_gap: float = 3.0, x_gap: float = 4.0):
    tiers = defaultdict(list)
    for n, data in topology.nodes(data=True):
        tiers[int(data.get("tier", 0))].append(n)
    pos = {}
    for tier in sorted(tiers):
        row = sorted(tiers[tier])
        x_start = -(len(row) - 1) * x_gap / 2.0
        for idx, n in enumerate(row):
            pos[n] = (x_start + idx * x_gap, tier * y_gap)
    return pos

# ---------------------------------------------------------------------------
# Public: drawFoldedClos
# ---------------------------------------------------------------------------

def drawFoldedClos(topology: nx.Graph, *, failed_link: Optional[Tuple[str, str]] = None, show_pristine: bool = True ) -> None:
    """Render the folded‑Clos topology.

    Parameters
    ----------
    topology : nx.Graph
        The folded‑Clos topology (undirected) produced by ClosGenerator.
    failed_link : tuple(str, str) | None, optional
        If provided, it must be `(u, v)` exactly matching an existing edge.
        A second figure is produced showing the link removed plus
        compute‑reachability colouring.  If *None* (default), only the
        pristine diagram is drawn and **no prompting** occurs.
    """

    # ---------- pristine diagram -----------------------------------------------------
    if(show_pristine):
        pos = _tier_layout(topology)
        plt.figure(figsize=(10, 6))
        nx.draw_networkx_edges(topology, pos, width=1.2, alpha=0.5)
        tier_colors = [topology.nodes[n]["tier"] for n in topology.nodes]
        nx.draw_networkx_nodes(topology, pos, node_color=tier_colors,
                            cmap=plt.cm.viridis, node_size=850)
        nx.draw_networkx_labels(topology, pos, font_size=8, font_color="white")
        plt.title("Folded‑Clos Topology")
        plt.axis("off")
        plt.tight_layout()
        plt.show()

    # ---------- optional failure view ------------------------------------------------
    if failed_link is None:
        return

    u, v = failed_link
    if not topology.has_edge(u, v):
        print(f"Warning: edge ({u}, {v}) not present – skipping failure diagram.")
        return

    topo_failed = deepcopy(topology)
    topo_failed.remove_edge(u, v)

    reach_status = _classify_nodes(_build_directed(topo_failed))

    pos_f = _tier_layout(topo_failed)
    plt.figure(figsize=(10, 6))
    nx.draw_networkx_edges(topo_failed, pos_f, width=1.2, alpha=0.4, edge_color="#bbbbbb")

    # highlight failure
    xs, ys = zip(pos_f[u], pos_f[v])
    plt.plot(xs, ys, linestyle="--", linewidth=2, color="#d62728", zorder=2)
    mx, my = (sum(xs) / 2, sum(ys) / 2)
    dx = dy = 0.4
    plt.plot([mx - dx, mx + dx], [my - dy, my + dy], color="#d62728", lw=2)
    plt.plot([mx - dx, mx + dx], [my + dy, my - dy], color="#d62728", lw=2)

    node_colors = ["#2ca02c" if reach_status[n] else "#d62728" for n in topo_failed.nodes]
    nx.draw_networkx_nodes(topo_failed, pos_f, node_color=node_colors,
                           edgecolors="black", node_size=850, linewidths=1.1)
    nx.draw_networkx_labels(topo_failed, pos_f, font_size=8, font_weight="bold")

    plt.title("After failure: compute reachability")
    plt.axis("off")
    plt.tight_layout()
    plt.show()

    impaired = sorted([n for n, ok in reach_status.items() if not ok])
    if impaired:
        print("Nodes that lost reachability to at least one compute device:")
        print("  " + ", ".join(impaired))
    else:
        print("All nodes can still reach every compute device via valley‑free paths.")
