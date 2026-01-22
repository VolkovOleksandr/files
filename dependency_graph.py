from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Union
from collections import defaultdict, deque
import heapq


NextStep = Union[None, str, Sequence[str]]


# ---------------------------- Exceptions ----------------------------

class GraphError(Exception):
    """Base class for dependency graph errors."""


class DuplicateNodeIdError(GraphError):
    """Raised when the same node id appears more than once across registries."""


class UnknownReferenceError(GraphError):
    """Raised when a nextStep points to a node id that doesn't exist."""


class CycleError(GraphError):
    """Raised when a cycle is detected."""

    def __init__(self, message: str, cycle_path: Optional[List[str]] = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []


# ---------------------------- Model ----------------------------

@dataclass(frozen=True, slots=True)
class Node:
    """
    Graph node.

    Fields used for graph logic:
      - id: node id (must be globally unique unless you prefix it)
      - kind: registry kind ("sql", "api", "event", ...)
      - next_step: None | str | list[str]

    meta:
      - preserves the original registry element structure INCLUDING id, nextStep, and injected kind
        (i.e., a "raw config" snapshot).
    """
    id: str
    kind: str
    next_step: NextStep = None
    meta: Mapping[str, Any] = None


# ---------------------------- Utility ----------------------------

class DependencyGraph:
    """
    Build a directed graph from multiple registries of items that contain:
      - id
      - optional nextStep (None | str | list[str])

    Supports:
      - downstream dependencies: what a node leads to
      - upstream dependents: what leads to a node
      - deterministic ordering:
          * downstream_ordered: start -> ... -> leaves (DFS topo on reachable subgraph)
          * upstream_ordered:   roots -> ... -> start (Kahn topo on upstream-induced subgraph)
      - validation:
          * duplicates
          * unknown references
          * cycle detection (global + per-query with cycle path)
    """

    def __init__(self, nodes: Dict[str, Node], forward: Dict[str, List[str]], reverse: Dict[str, List[str]]):
        self._nodes = nodes
        self._forward = forward
        self._reverse = reverse

    # ---------------------------- Construction ----------------------------

    @staticmethod
    def from_registries(
        registries: Mapping[str, Sequence[Mapping[str, Any]]],
        *,
        id_key: str = "id",
        next_key: str = "nextStep",
        strict: bool = True,
        validate_cycles: bool = True,
    ) -> "DependencyGraph":
        """
        registries example:
          {
            "sql":   [{"id":"sql1","nextStep":"api1","other":"data"}],
            "api":   [{"id":"api1","nextStep":null}],
            "event": [{"id":"e1","nextStep":"sql1"}],
          }

        strict:
          - True: unknown references raise UnknownReferenceError
          - False: unknown references are ignored in traversals (but still present in forward lists)

        validate_cycles:
          - True: validate the entire graph is acyclic at load time
        """
        nodes: Dict[str, Node] = {}

        def normalize_next(x: Any) -> List[str]:
            if x is None:
                return []
            if isinstance(x, str):
                return [x]
            if isinstance(x, (list, tuple)):
                return [str(v) for v in x]
            raise TypeError(f"{next_key} must be None, str, or list[str], got {type(x)}")

        # 1) Build nodes, preserving raw config in meta (including id, nextStep, and injected kind)
        for kind, items in registries.items():
            for idx, it in enumerate(items):
                if id_key not in it:
                    raise ValueError(f"Missing '{id_key}' in registry '{kind}' item at index {idx}: {it}")

                node_id = str(it[id_key])
                if node_id in nodes:
                    raise DuplicateNodeIdError(
                        f"Duplicate node id '{node_id}' found (registry='{kind}', index={idx}). "
                        "If ids can overlap across registries, use prefixed ids like 'sql:sql1'."
                    )

                raw = dict(it)          # snapshot original element
                raw["kind"] = str(kind) # inject kind to preserve origin

                nodes[node_id] = Node(
                    id=node_id,
                    kind=str(kind),
                    next_step=it.get(next_key),
                    meta=raw,
                )

        # 2) Build adjacency (deterministic, de-duped)
        forward: Dict[str, List[str]] = {}
        reverse_dd: Dict[str, List[str]] = defaultdict(list)

        for node_id, node in nodes.items():
            nxts = normalize_next(node.next_step)
            nxts = sorted(set(nxts))  # deterministic + de-dupe
            forward[node_id] = nxts

            for nxt in nxts:
                if strict and nxt not in nodes:
                    raise UnknownReferenceError(f"Unknown reference '{nxt}' from '{node_id}'")
                if nxt in nodes:
                    reverse_dd[nxt].append(node_id)

        for node_id in nodes:
            reverse_dd.setdefault(node_id, [])
        reverse: Dict[str, List[str]] = {k: sorted(set(v)) for k, v in reverse_dd.items()}

        g = DependencyGraph(nodes=nodes, forward=forward, reverse=reverse)

        if validate_cycles and strict:
            g._validate_no_cycles_global()

        return g

    # ---------------------------- Basic access ----------------------------

    def node(self, node_id: str) -> Node:
        self._ensure_exists(node_id)
        return self._nodes[node_id]

    def children(self, node_id: str) -> List[str]:
        self._ensure_exists(node_id)
        return list(self._forward.get(node_id, []))

    def parents(self, node_id: str) -> List[str]:
        self._ensure_exists(node_id)
        return list(self._reverse.get(node_id, []))

    def roots(self) -> List[str]:
        """Nodes with no incoming edges (not targeted by any nextStep)."""
        all_nodes = set(self._nodes.keys())
        targets: Set[str] = set()
        for u, nxts in self._forward.items():
            for v in nxts:
                if v in self._nodes:
                    targets.add(v)
        return sorted(all_nodes - targets)

    # ---------------------------- Closures (sets) ----------------------------

    def downstream_set(self, start_id: str) -> Set[str]:
        """All nodes reachable forward from start_id (includes start_id)."""
        self._ensure_exists(start_id)
        visited: Set[str] = {start_id}
        q = deque([start_id])
        while q:
            u = q.popleft()
            for v in self._forward.get(u, []):
                if v in self._nodes and v not in visited:
                    visited.add(v)
                    q.append(v)
        return visited

    def upstream_set(self, start_id: str) -> Set[str]:
        """All nodes that can reach start_id (includes start_id)."""
        self._ensure_exists(start_id)
        visited: Set[str] = {start_id}
        q = deque([start_id])
        while q:
            cur = q.popleft()
            for p in self._reverse.get(cur, []):
                if p not in visited:
                    visited.add(p)
                    q.append(p)
        return visited

    # ---------------------------- Ordered queries ----------------------------

    def downstream_ordered(self, start_id: str) -> List[str]:
        """
        Deterministic order start -> ... -> leaves (topological along reachable subgraph).
        Also returns helpful cycle path if a cycle is encountered.
        """
        self._ensure_exists(start_id)
        visited: Set[str] = set()
        stack: List[str] = []
        post: List[str] = []

        def dfs(u: str) -> None:
            if u in stack:
                cycle = self._extract_cycle(stack, u)
                raise CycleError(f"Cycle detected downstream starting from '{start_id}'", cycle_path=cycle)
            if u in visited:
                return

            stack.append(u)
            for v in self._forward.get(u, []):
                if v in self._nodes:
                    dfs(v)
            stack.pop()

            visited.add(u)
            post.append(u)

        dfs(start_id)
        return list(reversed(post))

    def upstream_ordered(self, start_id: str) -> List[str]:
        """
        Deterministic order roots -> ... -> start_id (topological sort on upstream-induced subgraph).
        Good for: "what depends on this, and in what safe order?"
        """
        self._ensure_exists(start_id)
        subset = self.upstream_set(start_id)
        return self._toposort_induced(subset, target=start_id)

    def describe(self, node_id: str) -> Dict[str, Any]:
        """Debug-friendly description including meta (raw config snapshot)."""
        n = self.node(node_id)
        return {
            "id": n.id,
            "kind": n.kind,
            "meta": dict(n.meta or {}),
            "parents": self.parents(node_id),
            "children": self.children(node_id),
            "upstream_ordered": self.upstream_ordered(node_id),
            "downstream_ordered": self.downstream_ordered(node_id),
        }

    # ---------------------------- Internals ----------------------------

    def _ensure_exists(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise KeyError(f"Unknown node id: {node_id}")

    @staticmethod
    def _extract_cycle(stack: List[str], repeated: str) -> List[str]:
        """
        stack: current DFS stack
        repeated: node that re-appeared
        Returns a cycle path like [b, c, d, b]
        """
        if repeated not in stack:
            return [repeated]
        i = stack.index(repeated)
        return stack[i:] + [repeated]

    def _toposort_induced(self, subset: Set[str], *, target: Optional[str] = None) -> List[str]:
        """
        Kahn's algorithm on the subgraph induced by `subset`, deterministic via heap.
        """
        indegree: Dict[str, int] = {u: 0 for u in subset}
        adj: Dict[str, List[str]] = {u: [] for u in subset}

        for u in subset:
            for v in self._forward.get(u, []):
                if v in subset:
                    adj[u].append(v)
                    indegree[v] += 1

        heap: List[str] = [u for u, deg in indegree.items() if deg == 0]
        heapq.heapify(heap)

        out: List[str] = []
        while heap:
            u = heapq.heappop(heap)
            out.append(u)
            for v in adj[u]:
                indegree[v] -= 1
                if indegree[v] == 0:
                    heapq.heappush(heap, v)

        if len(out) != len(subset):
            raise CycleError("Cycle detected in induced subgraph", cycle_path=[])

        # Optional sanity: ensure target is last-ish (it will appear after its ancestors anyway)
        return out

    def _validate_no_cycles_global(self) -> None:
        """
        Validate entire graph has no cycles using Kahn's algorithm.
        """
        indegree: Dict[str, int] = {u: 0 for u in self._nodes}

        for u, nxts in self._forward.items():
            for v in nxts:
                if v in self._nodes:
                    indegree[v] += 1

        q = deque([u for u, deg in indegree.items() if deg == 0])
        processed = 0

        while q:
            u = q.popleft()
            processed += 1
            for v in self._forward.get(u, []):
                if v in self._nodes:
                    indegree[v] -= 1
                    if indegree[v] == 0:
                        q.append(v)

        if processed != len(self._nodes):
            raise CycleError("Cycle detected in graph (global validation)", cycle_path=[])


# ---------------------------- Example usage ----------------------------

if __name__ == "__main__":
    registries = {
        "sql": [{"id": "sql1", "nextStep": "api1", "other": "dasta"}],
        "api": [{"id": "api1", "nextStep": None, "timeout": 30}],
        "event": [{"id": "e1", "nextStep": "sql1"}],
    }

    graph = DependencyGraph.from_registries(registries, strict=True)

    print(graph.describe("sql1"))
    # meta will include: {"id":"sql1","nextStep":"api1","other":"dasta","kind":"sql"}

    print("Upstream api1:", graph.upstream_ordered("api1"))     # ["e1","sql1","api1"]
    print("Downstream e1:", graph.downstream_ordered("e1"))     # ["e1","sql1","api1"]
    print("Roots:", graph.roots())                              # likely ["e1"]
