# External Libraries
import networkx as nx
import matplotlib.pyplot as plt

def drawFoldedClos(topology: nx.graph) -> None:
    """
    Parse a generated folded-Clos topology and draw it.
    """

    # Identify the tiers from 0 (compute tier) to N (top-tier switches)
    all_tiers = set()
    for node, attrs in topology.nodes(data=True):
        all_tiers.add(attrs["tier"])
    max_tier = max(all_tiers)
    min_tier = min(all_tiers)

    # Group nodes by tier
    tier_groups = {}
    for node, attrs in topology.nodes(data=True):
        t = attrs["tier"]
        tier_groups.setdefault(t, []).append(node)

    # Compute positions for each node to achieve a simple hierarchical layout
    # so that tier 0 is at y=0, tier 1 is at y=3, etc.
    pos = {}
    y_step = 3.0  # vertical spacing between tiers

    # Iterate tiers in ascending order: 0, 1, 2, ... so 0 is at the bottom
    for t in range(min_tier, max_tier + 1):
        # Skip if no nodes in that tier
        if t not in tier_groups:
            continue

        # All nodes at this tier
        nodes_at_tier = tier_groups[t]

        # Space these nodes horizontally. Adjust x_step for more or less spacing.
        x_step = 4.0
        x_start = -(len(nodes_at_tier) - 1) * x_step / 2.0

        print(f"TIER {t}")
        for i, node in enumerate(sorted(nodes_at_tier)):
            x_coord = x_start + i * x_step
            y_coord = t * y_step
            pos[node] = (x_coord, y_coord)
            print(f"\t{node}")

    # Draw the topology
    plt.figure(figsize=(12, 8))
    nx.draw_networkx_edges(topology, pos, alpha=0.5, width=1.0)

    # Color the nodes by tier for quick visual distinction
    node_colors = [topology.nodes[n]["tier"] for n in topology.nodes()]
    nx.draw_networkx_nodes(topology, pos,
                           node_color=node_colors,
                           cmap=plt.cm.viridis,
                           node_size=900)

    # Draw labels (node names inside nodes)
    nx.draw_networkx_labels(topology, pos, font_color='white', font_size=8)

    plt.title("Folded-Clos Topology")
    plt.axis('off')  # Hide the default x/y axes
    plt.show()

    return
