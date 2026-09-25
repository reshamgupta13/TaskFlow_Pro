import time
from datetime import date
import random
import pytest

from app.engine.dag_engine import DAGEngine
from app.engine.types import DependencyEdge, TaskColumn, TaskNode


def test_500_tasks_1000_edges_performance():
    """
    Stress test required by synopsis:
    - 500 tasks
    - 1,000 edges (forming a valid DAG)
    - Cycle check: under 10 ms
    - Status & schedule recalculation after a change: under 50 ms
    """
    num_tasks = 500
    num_edges = 1000
    base_date = date(2026, 1, 1)

    tasks = {}
    for i in range(num_tasks):
        t_id = f"task_{i:04d}"
        tasks[t_id] = TaskNode(
            id=t_id,
            title=f"Task {i}",
            column=TaskColumn.BACKLOG if i > 50 else TaskColumn.DONE,
            duration_days=random.randint(1, 5),
            planned_start=base_date,
        )

    # Construct a guaranteed DAG by only allowing edges from lower index to higher index
    # (i.e. task_j depends on task_i where i < j)
    edges = []
    edge_set = set()
    random.seed(42)

    while len(edges) < num_edges:
        i = random.randint(0, num_tasks - 2)
        j = random.randint(i + 1, num_tasks - 1)
        if (j, i) not in edge_set:
            edge_set.add((j, i))
            edges.append(DependencyEdge(task_id=f"task_{j:04d}", prerequisite_id=f"task_{i:04d}"))

    # Initial calculation
    t0 = time.perf_counter()
    DAGEngine.recompute_schedule(tasks, edges)
    init_duration_ms = (time.perf_counter() - t0) * 1000.0
    print(f"\nInitial 500-task full schedule calculation took: {init_duration_ms:.2f} ms")

    # 1. Benchmark Cycle Check: under 10 ms
    # Test valid edge check
    t_start = time.perf_counter()
    res_valid = DAGEngine.check_cycle_before_add(
        tasks, edges, new_task_id=f"task_{num_tasks-1:04d}", new_prerequisite_id="task_0000"
    )
    cycle_check_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"Cycle check (valid edge) on 500 tasks / 1000 edges took: {cycle_check_ms:.3f} ms")
    assert cycle_check_ms < 10.0, f"Cycle check took {cycle_check_ms:.2f}ms, target is < 10ms"

    # Test invalid edge (cycle) check
    t_start = time.perf_counter()
    res_invalid = DAGEngine.check_cycle_before_add(
        tasks, edges, new_task_id="task_0000", new_prerequisite_id=f"task_{num_tasks-1:04d}"
    )
    cycle_check_invalid_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"Cycle check (cycle detected) on 500 tasks / 1000 edges took: {cycle_check_invalid_ms:.3f} ms")
    assert not res_invalid.is_valid
    assert cycle_check_invalid_ms < 10.0, f"Cycle check invalid took {cycle_check_invalid_ms:.2f}ms, target is < 10ms"

    # 2. Benchmark Schedule Recalculation after a change: under 50 ms
    changed_task_id = "task_0010"
    tasks[changed_task_id].duration_days += 3

    t_start = time.perf_counter()
    res_recalc = DAGEngine.recompute_schedule(tasks, edges, changed_task_ids=[changed_task_id])
    recalc_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"Schedule recalculation after change affecting {len(res_recalc.affected_task_ids)} tasks took: {recalc_ms:.2f} ms")
    assert recalc_ms < 50.0, f"Recalculation took {recalc_ms:.2f}ms, target is < 50ms"
