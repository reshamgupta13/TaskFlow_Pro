from __future__ import annotations
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from app.engine.types import (
    CycleCheckResult,
    DependencyEdge,
    GraphScheduleResult,
    TaskColumn,
    TaskNode,
)


class DAGEngine:
    """
    Pure, independently testable DAG engine.
    Zero external database or framework dependencies.
    
    Guarantees:
    - Cycle prevention: O(V+E) reachability check with exact offending cycle path.
    - No compounding: Topological schedule recomputation ensures converging paths
      (e.g., diamond A->B->D, A->C->D) propagate exactly max delay, never the sum.
    - Derived status: Blocked vs Ready is strictly computed from prerequisite completion.
    - Rollback safety: Regressing a Done task flags downstream in-flight tasks and re-blocks others.
    - Critical path: Longest duration chain via DP over topological sort.
    """

    @staticmethod
    def build_adjacency(
        tasks: Dict[str, TaskNode],
        dependencies: List[DependencyEdge],
    ) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Builds prerequisites (in-edges) and dependents (out-edges) adjacency lists.
        prerequisites[task_id] = [prerequisite_ids...]
        dependents[prerequisite_id] = [task_ids...]
        """
        prereqs: Dict[str, List[str]] = {t_id: [] for t_id in tasks}
        dependents: Dict[str, List[str]] = {t_id: [] for t_id in tasks}

        for edge in dependencies:
            if edge.task_id in prereqs and edge.prerequisite_id in dependents:
                prereqs[edge.task_id].append(edge.prerequisite_id)
                dependents[edge.prerequisite_id].append(edge.task_id)

        return prereqs, dependents

    @classmethod
    def check_cycle_before_add(
        cls,
        tasks: Dict[str, TaskNode],
        existing_dependencies: List[DependencyEdge],
        new_task_id: str,
        new_prerequisite_id: str,
    ) -> CycleCheckResult:
        """
        Checks whether adding the edge (new_prerequisite_id -> new_task_id) would introduce a cycle.
        Returns CycleCheckResult with offending loop if rejected.
        Time complexity: O(V+E).
        """
        if new_task_id not in tasks:
            return CycleCheckResult(is_valid=False, message=f"Task '{new_task_id}' not found.")
        if new_prerequisite_id not in tasks:
            return CycleCheckResult(is_valid=False, message=f"Prerequisite '{new_prerequisite_id}' not found.")

        # Self-dependency check
        if new_task_id == new_prerequisite_id:
            return CycleCheckResult(
                is_valid=False,
                offending_loop=[new_task_id, new_task_id],
                message=f"Self-dependency rejected: Task '{new_task_id}' cannot depend on itself.",
            )

        # Duplicate edge check
        for edge in existing_dependencies:
            if edge.task_id == new_task_id and edge.prerequisite_id == new_prerequisite_id:
                return CycleCheckResult(
                    is_valid=False,
                    message=f"Duplicate edge: Task '{new_task_id}' already depends on '{new_prerequisite_id}'.",
                )

        # If adding prerequisite_id -> task_id, we must check if prerequisite_id is already
        # reachable from task_id via existing dependents edges.
        _, dependents = cls.build_adjacency(tasks, existing_dependencies)

        # BFS to find path from new_task_id to new_prerequisite_id
        parent_map: Dict[str, str] = {}
        visited: Set[str] = {new_task_id}
        queue = deque([new_task_id])
        found = False

        while queue:
            curr = queue.popleft()
            if curr == new_prerequisite_id:
                found = True
                break

            for nxt in dependents.get(curr, []):
                if nxt not in visited:
                    visited.add(nxt)
                    parent_map[nxt] = curr
                    queue.append(nxt)

        if found:
            # Reconstruct cycle: new_task_id -> ... -> new_prerequisite_id -> new_task_id
            path = [new_prerequisite_id]
            curr = new_prerequisite_id
            while curr != new_task_id:
                curr = parent_map[curr]
                path.append(curr)
            path.reverse()
            # Append new_task_id at the end to make loop explicit: T -> ... -> P -> T
            loop = path + [new_task_id]
            return CycleCheckResult(
                is_valid=False,
                offending_loop=loop,
                message=f"Cycle detected: Adding this dependency creates loop: {' -> '.join(loop)}",
            )

        return CycleCheckResult(is_valid=True)

    @classmethod
    def topological_sort(
        cls,
        tasks: Dict[str, TaskNode],
        prereqs: Dict[str, List[str]],
        dependents: Dict[str, List[str]],
        subset_ids: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Computes topological ordering using Kahn's algorithm.
        If subset_ids is provided, returns topological sort restricted to the subset.
        """
        target_ids = set(tasks.keys()) if subset_ids is None else set(subset_ids)
        in_degree: Dict[str, int] = {t_id: 0 for t_id in target_ids}

        for t_id in target_ids:
            for p_id in prereqs.get(t_id, []):
                if p_id in target_ids:
                    in_degree[t_id] += 1

        queue = deque([t_id for t_id, deg in in_degree.items() if deg == 0])
        topo_order: List[str] = []

        while queue:
            curr = queue.popleft()
            topo_order.append(curr)

            for child in dependents.get(curr, []):
                if child in in_degree:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)

        if len(topo_order) != len(target_ids):
            raise ValueError("Graph contains cycles or invalid dependencies during topological sort.")

        return topo_order

    @classmethod
    def compute_blocked_status(
        cls,
        tasks: Dict[str, TaskNode],
        prereqs: Dict[str, List[str]],
    ) -> None:
        """
        Derives Blocked/Ready status and rollback warnings in place.
        A task is Blocked if ANY prerequisite is not Done, else Ready.
        If a task is already in IN_PROGRESS or REVIEW and is Blocked, a regression warning is set.
        """
        for t_id, task in tasks.items():
            task_prereqs = prereqs.get(t_id, [])
            blocking_ids = []
            for p_id in task_prereqs:
                if p_id in tasks:
                    p_col = (
                        tasks[p_id].column.value
                        if isinstance(tasks[p_id].column, TaskColumn)
                        else str(tasks[p_id].column)
                    )
                    if p_col != "done":
                        blocking_ids.append(p_id)

            task.is_blocked = len(blocking_ids) > 0
            task.blocking_task_ids = blocking_ids

            curr_col = (
                task.column.value
                if isinstance(task.column, TaskColumn)
                else str(task.column)
            )

            if task.is_blocked and curr_col in ("in_progress", "review"):
                task.has_regression_warning = True
                task.warning_message = (
                    f"Warning: Task is {curr_col} but blocked by unfinished prerequisite(s): "
                    f"{', '.join(blocking_ids)}"
                )
            else:
                task.has_regression_warning = False
                task.warning_message = None

    @classmethod
    def recompute_schedule(
        cls,
        tasks: Dict[str, TaskNode],
        dependencies: List[DependencyEdge],
        changed_task_ids: Optional[List[str]] = None,
    ) -> GraphScheduleResult:
        """
        Recomputes schedule dates and blocked status for affected tasks.
        
        No-compounding algorithm:
        - If changed_task_ids is provided, finds the subgraph of descendants.
        - Descendants are ordered topologically.
        - Each descendant is evaluated EXACTLY ONCE.
        - start(T) = max(planned_start(T), latest end date among prerequisites).
        - end(T) = start(T) + duration_days calendar days.
        """
        prereqs, dependents = cls.build_adjacency(tasks, dependencies)

        # 1. Update Blocked / Ready / Warnings for all tasks
        cls.compute_blocked_status(tasks, prereqs)

        # 2. Determine affected tasks
        if changed_task_ids is None:
            # Recompute entire graph
            affected_ids = set(tasks.keys())
        else:
            # Find all reachable descendants of changed_task_ids
            affected_ids = set(changed_task_ids)
            queue = deque(changed_task_ids)
            while queue:
                curr = queue.popleft()
                for child in dependents.get(curr, []):
                    if child not in affected_ids:
                        affected_ids.add(child)
                        queue.append(child)

        # 3. Sort affected tasks topologically
        topo_order = cls.topological_sort(tasks, prereqs, dependents, subset_ids=affected_ids)

        # 4. Schedule calculation in topological order (no compounding)
        for t_id in topo_order:
            task = tasks[t_id]
            task_prereqs = prereqs.get(t_id, [])

            # Compute earliest possible start date from prerequisites
            candidate_start = task.planned_start

            for p_id in task_prereqs:
                p_task = tasks.get(p_id)
                if p_task and p_task.end_date:
                    if p_task.end_date > candidate_start:
                        candidate_start = p_task.end_date

            task.start_date = candidate_start
            task.end_date = candidate_start + timedelta(days=task.duration_days)

        # 5. Compute critical path across the entire graph
        critical_path = cls.compute_critical_path(tasks, prereqs, dependents)

        for t_id, task in tasks.items():
            task.is_critical_path = (t_id in critical_path)

        return GraphScheduleResult(
            updated_tasks=tasks,
            critical_path=critical_path,
            affected_task_ids=topo_order,
        )

    @classmethod
    def compute_critical_path(
        cls,
        tasks: Dict[str, TaskNode],
        prereqs: Dict[str, List[str]],
        dependents: Dict[str, List[str]],
    ) -> List[str]:
        """
        Computes the Critical Path (longest duration chain) via Dynamic Programming over topological order.
        Returns ordered list of task IDs on the critical path.
        """
        if not tasks:
            return []

        try:
            topo = cls.topological_sort(tasks, prereqs, dependents)
        except ValueError:
            return []

        # DP: dist[u] is the max duration of any path ending at u
        dist: Dict[str, int] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for u in topo:
            u_duration = tasks[u].duration_days
            max_p_dist = 0
            best_p: Optional[str] = None

            for p in prereqs.get(u, []):
                if p in dist and dist[p] > max_p_dist:
                    max_p_dist = dist[p]
                    best_p = p

            dist[u] = max_p_dist + u_duration
            predecessor[u] = best_p

        # Find the node with the maximum distance
        sink_node = max(dist.keys(), key=lambda k: dist[k], default=None)
        if not sink_node:
            return []

        # Reconstruct path by backtracking
        path: List[str] = []
        curr: Optional[str] = sink_node
        while curr is not None:
            path.append(curr)
            curr = predecessor.get(curr)

        path.reverse()
        return path

    @classmethod
    def validate_move(
        cls,
        task: TaskNode,
        target_column: TaskColumn,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a task can be moved to the target column.
        Rule from synopsis: Blocked tasks cannot be moved to In Progress, Review, or Done.
        """
        target_val = (
            target_column.value
            if isinstance(target_column, TaskColumn)
            else str(target_column)
        )
        if task.is_blocked and target_val in ("in_progress", "review", "done"):
            return (
                False,
                f"Cannot move Blocked task '{task.title}' to {target_val.replace('_', ' ').title()}. "
                f"Unmet prerequisites: {', '.join(task.blocking_task_ids)}",
            )
        return True, None
