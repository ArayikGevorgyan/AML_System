"""
Network Anomaly Detector
==========================
Detects anomalous nodes and edges in AML transaction networks using
statistical methods and (optionally) an Isolation Forest approach.

The detector works on graph data produced by analysis.network_analysis
and flags entities whose network behavior is statistically unusual.

Usage:
    from ml.network_anomaly_detector import NetworkAnomalyDetector
    from analysis.network_analysis import build_transaction_graph
    from database import SessionLocal

    db = SessionLocal()
    detector = NetworkAnomalyDetector()
    graph = build_transaction_graph(db, days=30)
    detector.fit(graph)
    anomalies = detector.get_anomaly_report()
"""

import json
import math
import logging
import statistics
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class NetworkAnomalyDetector:
    """
    Detects anomalous nodes and edges in AML transaction networks.

    Uses a two-stage approach:
      1. Statistical outlier detection (IQR / Z-score) on node features
      2. Isolation Forest-style anomaly scoring using node feature vectors

    Attributes:
        graph:          The fitted transaction graph dict.
        node_features:  Computed feature dict per node.
        anomalous_nodes: Set of flagged node IDs.
        anomalous_edges: List of flagged edge dicts.
        fitted:         Whether fit() has been called.
    """

    def __init__(
        self,
        contamination: float = 0.1,
        z_score_threshold: float = 2.5,
    ) -> None:
        """
        Initialize the detector.

        Args:
            contamination:     Expected fraction of anomalies (for IF-style scoring).
            z_score_threshold: Z-score threshold for outlier detection.
        """
        self.contamination = contamination
        self.z_score_threshold = z_score_threshold
        self.graph: Dict[str, Any] = {}
        self.node_features: Dict[int, List[float]] = {}
        self.anomalous_nodes: List[Dict[str, Any]] = []
        self.anomalous_edges: List[Dict[str, Any]] = []
        self.fitted: bool = False
        self._feature_stats: Dict[str, Dict[str, float]] = {}

    # ---------------------------------------------------------------------------
    # fit
    # ---------------------------------------------------------------------------

    def fit(self, transaction_graph: Dict[str, Any]) -> "NetworkAnomalyDetector":
        """
        Fit the anomaly detector on a pre-built transaction graph.

        Computes node features, fits statistical baselines, and identifies
        initial anomaly candidates.

        Args:
            transaction_graph: Output dict from build_transaction_graph().

        Returns:
            self (for chaining)
        """
        self.graph = transaction_graph
        nodes = transaction_graph.get("nodes", {})
        edges = transaction_graph.get("edges", [])

        if not nodes:
            logger.warning("NetworkAnomalyDetector.fit() called with empty graph.")
            self.fitted = True
            return self

        # Compute node features
        self.node_features = self.compute_node_features(transaction_graph)

        # Compute per-feature statistics for anomaly scoring
        feature_keys = ["out_degree", "in_degree", "total_sent", "total_received",
                        "degree_ratio", "amount_ratio"]
        for fk in feature_keys:
            vals = [
                feat[i] for feat in self.node_features.values()
                for i, k in enumerate(feature_keys) if k == fk
            ]
            if vals and len(vals) > 1:
                self._feature_stats[fk] = {
                    "mean": statistics.mean(vals),
                    "std": statistics.stdev(vals) if len(vals) > 1 else 1.0,
                    "q1": sorted(vals)[len(vals) // 4],
                    "q3": sorted(vals)[(3 * len(vals)) // 4],
                }

        # Detect anomalies
        self.anomalous_nodes = self.detect_anomalous_nodes(transaction_graph)
        self.anomalous_edges = self.detect_anomalous_edges(transaction_graph)

        self.fitted = True
        logger.info(
            "NetworkAnomalyDetector fitted: %d nodes, %d anomalous nodes, %d anomalous edges",
            len(nodes), len(self.anomalous_nodes), len(self.anomalous_edges)
        )
        return self

    # ---------------------------------------------------------------------------
    # compute_node_features
    # ---------------------------------------------------------------------------

    def compute_node_features(
        self, graph: Dict[str, Any]
    ) -> Dict[int, List[float]]:
        """
        Compute a numerical feature vector for each node in the graph.

        Features per node (6 total):
          0: out_degree (normalized by max)
          1: in_degree  (normalized by max)
          2: log(total_sent + 1)
          3: log(total_received + 1)
          4: degree_ratio  (out / (in + 1))
          5: amount_ratio  (sent / (received + 1))

        Args:
            graph: Transaction graph dict from build_transaction_graph().

        Returns:
            Dict mapping node_id → List[float] feature vector.
        """
        nodes = graph.get("nodes", {})
        if not nodes:
            return {}

        max_out = max((d["out_degree"] for d in nodes.values()), default=1) or 1
        max_in = max((d["in_degree"] for d in nodes.values()), default=1) or 1

        features = {}
        for nid, data in nodes.items():
            out_d = data.get("out_degree", 0)
            in_d = data.get("in_degree", 0)
            sent = data.get("total_sent", 0.0) or 0.0
            received = data.get("total_received", 0.0) or 0.0

            out_norm = out_d / max_out
            in_norm = in_d / max_in
            log_sent = math.log(sent + 1)
            log_recv = math.log(received + 1)
            degree_ratio = out_d / (in_d + 1)
            amount_ratio = sent / (received + 1)

            features[int(nid)] = [
                round(out_norm, 4),
                round(in_norm, 4),
                round(log_sent, 4),
                round(log_recv, 4),
                round(degree_ratio, 4),
                round(amount_ratio, 4),
            ]

        return features

    # ---------------------------------------------------------------------------
    # detect_anomalous_nodes
    # ---------------------------------------------------------------------------

    def detect_anomalous_nodes(self, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify anomalous nodes using Z-score outlier detection on each feature.

        A node is flagged if ANY of its feature values exceeds z_score_threshold
        standard deviations from the mean.

        Args:
            graph: Transaction graph dict.

        Returns:
            List of anomalous node dicts with explanations.
        """
        nodes = graph.get("nodes", {})
        if not nodes:
            return []

        node_feats = self.compute_node_features(graph) if not self.node_features else self.node_features
        feature_names = ["out_degree", "in_degree", "log_sent", "log_received",
                         "degree_ratio", "amount_ratio"]

        # Compute per-feature stats
        per_feat_stats: Dict[int, Dict] = {}
        for fi in range(6):
            vals = [fv[fi] for fv in node_feats.values() if len(fv) > fi]
            if len(vals) < 2:
                per_feat_stats[fi] = {"mean": 0.0, "std": 1.0}
                continue
            per_feat_stats[fi] = {
                "mean": statistics.mean(vals),
                "std": statistics.stdev(vals) or 1.0,
            }

        anomalous = []
        for nid, feat_vec in node_feats.items():
            reasons = []
            max_z = 0.0
            for fi, fval in enumerate(feat_vec):
                mean = per_feat_stats.get(fi, {}).get("mean", 0.0)
                std = per_feat_stats.get(fi, {}).get("std", 1.0)
                z = abs(fval - mean) / std if std > 0 else 0.0
                if z > self.z_score_threshold:
                    reasons.append({
                        "feature": feature_names[fi] if fi < len(feature_names) else f"feat_{fi}",
                        "value": round(fval, 4),
                        "z_score": round(z, 3),
                    })
                    max_z = max(max_z, z)

            if reasons:
                node_data = nodes.get(str(nid)) or nodes.get(nid, {})
                anomalous.append({
                    "node_id": nid,
                    "anomaly_reasons": reasons,
                    "max_z_score": round(max_z, 3),
                    "out_degree": node_data.get("out_degree", 0),
                    "in_degree": node_data.get("in_degree", 0),
                    "total_sent": node_data.get("total_sent", 0.0),
                    "total_received": node_data.get("total_received", 0.0),
                })

        return sorted(anomalous, key=lambda x: x["max_z_score"], reverse=True)

    # ---------------------------------------------------------------------------
    # detect_anomalous_edges
    # ---------------------------------------------------------------------------

    def detect_anomalous_edges(self, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify anomalous edges (transaction flows between node pairs).

        An edge is anomalous if its total_amount or txn_count is a statistical
        outlier relative to all other edges.

        Args:
            graph: Transaction graph dict.

        Returns:
            List of anomalous edge dicts.
        """
        edges = graph.get("edges", [])
        if len(edges) < 3:
            return []

        amounts = [e.get("total_amount", 0.0) for e in edges]
        counts = [e.get("txn_count", 0) for e in edges]

        if len(amounts) < 2:
            return []

        mean_amt = statistics.mean(amounts)
        std_amt = statistics.stdev(amounts) or 1.0
        mean_cnt = statistics.mean(counts)
        std_cnt = statistics.stdev(counts) or 1.0

        anomalous = []
        for edge in edges:
            edge_amt = edge.get("total_amount", 0.0)
            edge_cnt = edge.get("txn_count", 0)

            z_amt = abs(edge_amt - mean_amt) / std_amt
            z_cnt = abs(edge_cnt - mean_cnt) / std_cnt

            if z_amt > self.z_score_threshold or z_cnt > self.z_score_threshold:
                anomalous.append({
                    "from_id": edge.get("from_id"),
                    "to_id": edge.get("to_id"),
                    "total_amount": edge_amt,
                    "txn_count": edge_cnt,
                    "amount_z_score": round(z_amt, 3),
                    "count_z_score": round(z_cnt, 3),
                    "anomaly_type": (
                        "high_amount" if z_amt > z_cnt else "high_frequency"
                    ),
                })

        return sorted(anomalous, key=lambda x: x["amount_z_score"], reverse=True)

    # ---------------------------------------------------------------------------
    # isolation_forest_detect
    # ---------------------------------------------------------------------------

    def isolation_forest_detect(
        self, features: List[List[float]]
    ) -> List[Dict[str, Any]]:
        """
        Approximate Isolation Forest anomaly scoring without sklearn dependency.

        Scores samples by measuring how quickly they are isolated via random
        feature splits. Lower isolation depth = more anomalous.

        Args:
            features: List of feature vectors (each List[float]).

        Returns:
            List of dicts: [{index, anomaly_score, is_anomaly}]
        """
        if not features:
            return []

        n = len(features)
        n_features = len(features[0]) if features else 0
        if n_features == 0:
            return []

        def random_isolation_depth(sample: List[float], data: List[List[float]], max_depth: int) -> float:
            """Compute average isolation depth via random feature splits."""
            depths = []
            for _ in range(min(10, n)):  # 10 random trees
                depth = 0
                remaining = list(range(len(data)))
                point_isolated = False

                while depth < max_depth and len(remaining) > 1:
                    feat_idx = depth % n_features
                    col_vals = [data[i][feat_idx] for i in remaining]
                    if not col_vals or max(col_vals) == min(col_vals):
                        break

                    split = (max(col_vals) + min(col_vals)) / 2
                    left = [i for i in remaining if data[i][feat_idx] <= split]
                    right = [i for i in remaining if data[i][feat_idx] > split]

                    if sample[feat_idx] <= split:
                        remaining = left
                    else:
                        remaining = right
                    depth += 1

                    if len(remaining) <= 1:
                        point_isolated = True
                        break

                depths.append(depth)

            return statistics.mean(depths) if depths else max_depth

        max_depth = int(math.log2(n)) + 1 if n > 1 else 1
        avg_depth = max_depth / 2

        results = []
        for i, sample in enumerate(features):
            depth = random_isolation_depth(sample, features, max_depth)
            # Shorter path = more anomalous; score in [0, 1], higher = more anomalous
            score = 2 ** (-depth / avg_depth) if avg_depth > 0 else 0.5
            is_anomaly = score > (1 - self.contamination)
            results.append({
                "index": i,
                "anomaly_score": round(score, 4),
                "is_anomaly": is_anomaly,
            })

        return sorted(results, key=lambda x: x["anomaly_score"], reverse=True)

    # ---------------------------------------------------------------------------
    # flag_anomalies
    # ---------------------------------------------------------------------------

    def flag_anomalies(self, db: Any) -> Dict[str, Any]:
        """
        Run full anomaly detection against live database transaction graph.

        Builds the transaction graph, fits the detector, and returns
        a structured summary of all detected network anomalies.

        Args:
            db: SQLAlchemy session.

        Returns:
            Anomaly detection summary dict.
        """
        from analysis.network_analysis import build_transaction_graph

        graph = build_transaction_graph(db, days=30)
        self.fit(graph)
        return self.get_anomaly_report()

    # ---------------------------------------------------------------------------
    # get_anomaly_report
    # ---------------------------------------------------------------------------

    def get_anomaly_report(self) -> Dict[str, Any]:
        """
        Return a comprehensive summary of detected network anomalies.

        Returns:
            Dict containing:
                - generated_at: str
                - graph_stats: {node_count, edge_count}
                - anomalous_nodes: List (sorted by max_z_score)
                - anomalous_edges: List (sorted by amount_z_score)
                - anomalous_node_count: int
                - anomalous_edge_count: int
                - high_severity_nodes: List (max_z_score > 5.0)

        Raises:
            RuntimeError: If fit() has not been called.
        """
        if not self.fitted:
            raise RuntimeError("NetworkAnomalyDetector must be fitted before get_anomaly_report().")

        high_sev = [n for n in self.anomalous_nodes if n["max_z_score"] > 5.0]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "graph_stats": {
                "node_count": self.graph.get("node_count", 0),
                "edge_count": self.graph.get("edge_count", 0),
                "total_volume": self.graph.get("total_volume", 0.0),
            },
            "anomalous_node_count": len(self.anomalous_nodes),
            "anomalous_edge_count": len(self.anomalous_edges),
            "high_severity_node_count": len(high_sev),
            "anomalous_nodes": self.anomalous_nodes[:25],
            "anomalous_edges": self.anomalous_edges[:25],
            "high_severity_nodes": high_sev,
        }

    def __repr__(self) -> str:
        status = "fitted" if self.fitted else "unfitted"
        return (
            f"NetworkAnomalyDetector({status}, "
            f"contamination={self.contamination}, "
            f"z_threshold={self.z_score_threshold})"
        )
