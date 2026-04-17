"""
Network Analysis Module
========================
Detects transaction network patterns associated with money laundering:
  - Circular transaction flows (layering)
  - Hub accounts with many connections
  - Connected components in the transaction graph
  - Rapid movement through intermediary accounts
  - Centrality scores without external graph library dependencies

All graph logic is implemented with plain Python dicts/sets.

Usage:
    from database import SessionLocal
    from analysis.network_analysis import build_transaction_graph, find_circular_transactions

    db = SessionLocal()
    graph = build_transaction_graph(db, days=30)
    circles = find_circular_transactions(db, days=30)
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session

from models.transaction import Transaction
from models.customer import Customer


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Graph data structures
# ---------------------------------------------------------------------------

# A graph is represented as:
#   {node_id: {"out": {neighbor_id, ...}, "in": {neighbor_id, ...}}}
# where node_id is a customer_id integer.

GraphType = Dict[int, Dict[str, Set[int]]]
EdgeType = Tuple[int, int, float, str]   # (from_id, to_id, amount, txn_ref)


def _empty_node() -> Dict[str, Any]:
    return {"out": set(), "in": set(), "amounts": [], "txn_count": 0}


# ---------------------------------------------------------------------------
# build_transaction_graph
# ---------------------------------------------------------------------------

def build_transaction_graph(db: Session, days: int = 30) -> Dict[str, Any]:
    """
    Build an adjacency-set transaction graph from recent transactions.

    Only transfers between distinct customers are included (not self-loops).
    Both directed edges and edge weights (total amount) are captured.

    Args:
        db:   SQLAlchemy session.
        days: Lookback window in days.

    Returns:
        Dict containing:
            - nodes: Dict[int, {out_degree, in_degree, total_sent, total_received}]
            - edges: List[{from_id, to_id, total_amount, txn_count}]
            - node_count: int
            - edge_count: int
            - total_volume: float
    """
    cutoff = _now() - timedelta(days=days)
    txns = db.query(Transaction).filter(
        Transaction.created_at >= cutoff,
        Transaction.from_customer_id.isnot(None),
        Transaction.to_customer_id.isnot(None),
    ).all()

    nodes: Dict[int, Dict] = {}
    # edge_map: (from_id, to_id) -> {total_amount, txn_count}
    edge_map: Dict[Tuple[int, int], Dict] = {}

    for t in txns:
        f = t.from_customer_id
        to = t.to_customer_id
        if f is None or to is None or f == to:
            continue

        # Nodes
        if f not in nodes:
            nodes[f] = {"out": set(), "in": set(), "total_sent": 0.0, "total_received": 0.0}
        if to not in nodes:
            nodes[to] = {"out": set(), "in": set(), "total_sent": 0.0, "total_received": 0.0}

        nodes[f]["out"].add(to)
        nodes[to]["in"].add(f)
        nodes[f]["total_sent"] += t.amount or 0
        nodes[to]["total_received"] += t.amount or 0

        key = (f, to)
        if key not in edge_map:
            edge_map[key] = {"from_id": f, "to_id": to, "total_amount": 0.0, "txn_count": 0}
        edge_map[key]["total_amount"] += t.amount or 0
        edge_map[key]["txn_count"] += 1

    # Build serialisable node summary
    node_summary = {}
    for nid, data in nodes.items():
        node_summary[nid] = {
            "out_degree": len(data["out"]),
            "in_degree": len(data["in"]),
            "total_sent": round(data["total_sent"], 2),
            "total_received": round(data["total_received"], 2),
        }

    edges = list(edge_map.values())
    total_volume = sum(e["total_amount"] for e in edges)

    return {
        "nodes": node_summary,
        "edges": edges,
        "node_count": len(node_summary),
        "edge_count": len(edges),
        "total_volume": round(total_volume, 2),
    }


# ---------------------------------------------------------------------------
# find_circular_transactions
# ---------------------------------------------------------------------------

def find_circular_transactions(db: Session, days: int = 30, max_hops: int = 5) -> List[Dict[str, Any]]:
    """
    Detect circular transaction flows (A→B→C→A) which indicate layering.

    Uses iterative DFS to find cycles up to max_hops in length.

    Args:
        db:       SQLAlchemy session.
        days:     Lookback window.
        max_hops: Maximum cycle length to detect (default 5).

    Returns:
        List of detected cycle dicts:
            [{cycle_nodes: [int], hop_count: int, cycle_str: str}]
    """
    graph_data = build_transaction_graph(db, days)
    edges = graph_data.get("edges", [])

    # Build adjacency list
    adj: Dict[int, Set[int]] = {}
    for edge in edges:
        f = edge["from_id"]
        t = edge["to_id"]
        if f not in adj:
            adj[f] = set()
        adj[f].add(t)

    all_nodes = set(adj.keys())
    detected_cycles: List[Tuple] = []
    seen_cycles: Set[Tuple] = set()

    def dfs(start: int, current: int, path: List[int]):
        if len(path) > max_hops:
            return
        for neighbor in adj.get(current, set()):
            if neighbor == start and len(path) >= 2:
                cycle = tuple(path + [start])
                canonical = tuple(sorted(cycle[:-1]))
                if canonical not in seen_cycles:
                    seen_cycles.add(canonical)
                    detected_cycles.append(list(path) + [start])
            elif neighbor not in path and neighbor in all_nodes:
                dfs(start, neighbor, path + [neighbor])

    for node in all_nodes:
        dfs(node, node, [node])

    result = []
    for cycle in detected_cycles[:50]:  # limit output
        result.append({
            "cycle_nodes": cycle,
            "hop_count": len(cycle) - 1,
            "cycle_str": " → ".join(str(n) for n in cycle),
        })

    return result


# ---------------------------------------------------------------------------
# identify_hub_accounts
# ---------------------------------------------------------------------------

def identify_hub_accounts(db: Session, min_connections: int = 5) -> List[Dict[str, Any]]:
    """
    Identify customer accounts that act as hubs — receiving from many sources
    and/or sending to many destinations. Hubs can indicate smurfing aggregation
    points or integration nodes.

    Args:
        db:              SQLAlchemy session.
        min_connections: Minimum total (in + out) unique connections threshold.

    Returns:
        List of hub customer dicts:
            [{customer_id, full_name, in_degree, out_degree, total_degree,
              total_sent, total_received, risk_level}]
        Sorted by total_degree descending.
    """
    graph_data = build_transaction_graph(db, days=90)
    nodes = graph_data.get("nodes", {})

    hubs = []
    for cid, data in nodes.items():
        total_degree = data["in_degree"] + data["out_degree"]
        if total_degree >= min_connections:
            customer = db.query(Customer).filter(Customer.id == cid).first()
            name = customer.full_name if customer else f"Customer {cid}"
            risk = customer.risk_level if customer else "unknown"

            hubs.append({
                "customer_id": cid,
                "full_name": name,
                "in_degree": data["in_degree"],
                "out_degree": data["out_degree"],
                "total_degree": total_degree,
                "total_sent": data["total_sent"],
                "total_received": data["total_received"],
                "risk_level": risk,
            })

    return sorted(hubs, key=lambda x: x["total_degree"], reverse=True)


# ---------------------------------------------------------------------------
# detect_layering_patterns
# ---------------------------------------------------------------------------

def detect_layering_patterns(db: Session) -> List[Dict[str, Any]]:
    """
    Detect potential layering by finding chains of transactions where funds
    move rapidly through multiple accounts, with each hop changing the amount
    by less than 10% (structuring disguise).

    Args:
        db: SQLAlchemy session.

    Returns:
        List of layering candidates:
            [{chain_length, customer_ids, total_amount, start_ref, end_ref}]
    """
    cutoff = _now() - timedelta(days=30)
    txns = db.query(Transaction).filter(
        Transaction.created_at >= cutoff,
        Transaction.from_customer_id.isnot(None),
        Transaction.to_customer_id.isnot(None),
    ).order_by(Transaction.created_at).all()

    # Index transactions by sender
    by_sender: Dict[int, List] = {}
    for t in txns:
        sid = t.from_customer_id
        if sid not in by_sender:
            by_sender[sid] = []
        by_sender[sid].append(t)

    layering_chains = []

    def follow_chain(txn, path: List, visited: Set[int]):
        if len(path) > 8:
            return
        recipient = txn.to_customer_id
        if recipient in visited:
            return
        visited.add(recipient)
        next_txns = by_sender.get(recipient, [])
        for next_t in next_txns:
            time_diff = (next_t.created_at - txn.created_at).total_seconds()
            if 0 < time_diff < 86400:  # within 24 hours
                amount_ratio = abs(next_t.amount - txn.amount) / txn.amount if txn.amount else 1
                if amount_ratio < 0.15:  # similar amount (possible layering)
                    new_path = path + [next_t]
                    if len(new_path) >= 2:
                        customer_ids = [path[0].from_customer_id] + [t.to_customer_id for t in new_path]
                        layering_chains.append({
                            "chain_length": len(new_path),
                            "customer_ids": customer_ids,
                            "total_amount": round(sum(t.amount for t in new_path), 2),
                            "start_ref": path[0].reference,
                            "end_ref": new_path[-1].reference,
                        })
                    follow_chain(next_t, new_path, visited)

    for txn in txns[:200]:  # limit to avoid O(n^2)
        follow_chain(txn, [txn], {txn.from_customer_id})

    # Deduplicate by start_ref + chain_length
    seen = set()
    unique = []
    for chain in layering_chains:
        key = (chain["start_ref"], chain["chain_length"])
        if key not in seen:
            seen.add(key)
            unique.append(chain)

    return unique[:30]


# ---------------------------------------------------------------------------
# compute_centrality_scores
# ---------------------------------------------------------------------------

def compute_centrality_scores(
    nodes: Dict[int, Dict[str, int]],
    edges: List[Dict[str, Any]],
) -> Dict[int, Dict[str, float]]:
    """
    Compute simple degree centrality and betweenness approximation for
    all nodes in a pre-built graph.

    Degree centrality = (in_degree + out_degree) / (N - 1)
    Betweenness is approximated as the fraction of edges passing through a node.

    Args:
        nodes: Node dict from build_transaction_graph()["nodes"].
        edges: Edge list from build_transaction_graph()["edges"].

    Returns:
        Dict[node_id, {degree_centrality, in_centrality, out_centrality,
                        edge_betweenness_approx}]
    """
    n = len(nodes)
    if n <= 1:
        return {}

    # Count how many times each node appears as intermediate in paths
    betweenness_approx: Dict[int, int] = {nid: 0 for nid in nodes}
    for edge in edges:
        # A simple proxy: nodes appearing in both in and out sets of edges are intermediaries
        f = edge["from_id"]
        t = edge["to_id"]
        if f in betweenness_approx:
            betweenness_approx[f] += 1
        if t in betweenness_approx:
            betweenness_approx[t] += 1

    max_between = max(betweenness_approx.values()) if betweenness_approx else 1

    result = {}
    for nid, data in nodes.items():
        total_degree = data["in_degree"] + data["out_degree"]
        result[nid] = {
            "degree_centrality": round(total_degree / (n - 1), 4),
            "in_centrality": round(data["in_degree"] / (n - 1), 4),
            "out_centrality": round(data["out_degree"] / (n - 1), 4),
            "edge_betweenness_approx": round(
                betweenness_approx[nid] / max_between, 4
            ) if max_between > 0 else 0.0,
        }

    return result


# ---------------------------------------------------------------------------
# find_connected_components
# ---------------------------------------------------------------------------

def find_connected_components(db: Session) -> Dict[str, Any]:
    """
    Find connected components in the undirected transaction graph.

    Components are groups of customers who have directly or indirectly
    transacted with each other. Large components may warrant group-level
    investigation.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - component_count: int
            - largest_component_size: int
            - components: List[{id, size, members: List[int]}]
              (only components with size >= 2)
            - isolated_node_count: int
    """
    graph_data = build_transaction_graph(db, days=90)
    nodes = graph_data.get("nodes", {})
    edges = graph_data.get("edges", [])

    # Build undirected adjacency
    adj: Dict[int, Set[int]] = {nid: set() for nid in nodes}
    for edge in edges:
        f = edge["from_id"]
        t = edge["to_id"]
        if f in adj:
            adj[f].add(t)
        if t in adj:
            adj[t].add(f)

    all_nodes = set(nodes.keys())
    visited: Set[int] = set()
    components: List[List[int]] = []

    def bfs(start: int) -> List[int]:
        component = []
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor in adj.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        return component

    for node in all_nodes:
        if node not in visited:
            component = bfs(node)
            components.append(component)

    components.sort(key=len, reverse=True)
    isolated = sum(1 for c in components if len(c) == 1)
    multi_components = [
        {"id": i + 1, "size": len(c), "members": c}
        for i, c in enumerate(components)
        if len(c) >= 2
    ]

    return {
        "component_count": len(components),
        "largest_component_size": len(components[0]) if components else 0,
        "components": multi_components[:20],  # return top 20
        "isolated_node_count": isolated,
    }
