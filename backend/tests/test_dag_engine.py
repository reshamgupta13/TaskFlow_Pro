from datetime import date, timedelta
import pytest

from app.engine.dag_engine import DAGEngine
from app.engine.types import (
    DependencyEdge,
    DependencySource,
    TaskColumn,
    TaskNode,
)


def create_sample_task(
    task_id: str,
    title: str,
    column: TaskColumn = TaskColumn.BACKLOG,
    duration_days: int = 2,
    planned_start: date = date(2026, 3, 1),
) -> TaskNode:
    return TaskNode(
        id=task_id,
        title=title,
        column=column,
        duration_days=duration_days,
        planned_start=planned_start,
    )


class TestCycleDetection:
    def test_self_dependency_rejected(self):
        tasks = {"A": create_sample_task("A", "Task A")}
        res = DAGEngine.check_cycle_before_add(tasks, [], new_task_id="A", new_prerequisite_id="A")
        assert not res.is_valid
        assert res.offending_loop == ["A", "A"]
        assert "Self-dependency rejected" in (res.message or "")

    def test_direct_cycle_rejected(self):
        # A -> B (B depends on A)
        # Attempt to add B -> A (A depends on B)
        tasks = {
            "A": create_sample_task("A", "Task A"),
            "B": create_sample_task("B", "Task B"),
        }
        edges = [DependencyEdge(task_id="B", prerequisite_id="A")]

        res = DAGEngine.check_cycle_before_add(
            tasks, edges, new_task_id="A", new_prerequisite_id="B"
        )
        assert not res.is_valid
        assert res.offending_loop == ["A", "B", "A"]
        assert "Cycle detected" in (res.message or "")

    def test_transitive_cycle_rejected(self):
        # A -> B -> C (C depends on B, B depends on A)
        # Attempt C -> A (A depends on C) creates A -> B -> C -> A
        tasks = {
            "A": create_sample_task("A", "Task A"),
            "B": create_sample_task("B", "Task B"),
            "C": create_sample_task("C", "Task C"),
        }
        edges = [
            DependencyEdge(task_id="B", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="B"),
        ]

        res = DAGEngine.check_cycle_before_add(
            tasks, edges, new_task_id="A", new_prerequisite_id="C"
        )
        assert not res.is_valid
        assert res.offending_loop == ["A", "B", "C", "A"]

    def test_diamond_valid_no_cycle(self):
        # A -> B -> D and A -> C -> D (Valid diamond)
        tasks = {
            "A": create_sample_task("A", "Task A"),
            "B": create_sample_task("B", "Task B"),
            "C": create_sample_task("C", "Task C"),
            "D": create_sample_task("D", "Task D"),
        }
        edges = [
            DependencyEdge(task_id="B", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="A"),
            DependencyEdge(task_id="D", prerequisite_id="B"),
        ]
        # Adding C -> D (D depends on C) is completely valid
        res = DAGEngine.check_cycle_before_add(
            tasks, edges, new_task_id="D", new_prerequisite_id="C"
        )
        assert res.is_valid
        assert res.offending_loop is None


class TestNoCompoundingScheduling:
    def test_diamond_no_compounding(self):
        """
        Critical requirement test:
        Diamond: A -> B -> D and A -> C -> D.
        A 3-day slip in A must move D by 3 days, not 6.
        """
        base_date = date(2026, 3, 1)
        tasks = {
            "A": create_sample_task("A", "Schema", duration_days=3, planned_start=base_date),
            "B": create_sample_task("B", "Backend API", duration_days=2, planned_start=base_date),
            "C": create_sample_task("C", "Frontend Shell", duration_days=4, planned_start=base_date),
            "D": create_sample_task("D", "Integration Tests", duration_days=2, planned_start=base_date),
        }
        edges = [
            DependencyEdge(task_id="B", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="A"),
            DependencyEdge(task_id="D", prerequisite_id="B"),
            DependencyEdge(task_id="D", prerequisite_id="C"),
        ]

        # Initial schedule
        res1 = DAGEngine.recompute_schedule(tasks, edges)
        # A: 2026-03-01 to 2026-03-04 (3 days)
        assert tasks["A"].start_date == date(2026, 3, 1)
        assert tasks["A"].end_date == date(2026, 3, 4)
        # B: start = 2026-03-04, end = 2026-03-06 (2 days)
        assert tasks["B"].start_date == date(2026, 3, 4)
        assert tasks["B"].end_date == date(2026, 3, 6)
        # C: start = 2026-03-04, end = 2026-03-08 (4 days)
        assert tasks["C"].start_date == date(2026, 3, 4)
        assert tasks["C"].end_date == date(2026, 3, 8)
        # D: start = max(end(B)=03-06, end(C)=03-08) = 2026-03-08, end = 2026-03-10
        assert tasks["D"].start_date == date(2026, 3, 8)
        assert tasks["D"].end_date == date(2026, 3, 10)

        # Now Task A slips by 3 days: duration increases by 3 (from 3 to 6 days)
        tasks["A"].duration_days = 6
        res2 = DAGEngine.recompute_schedule(tasks, edges, changed_task_ids=["A"])

        # A: end = 2026-03-07 (+3 days)
        assert tasks["A"].end_date == date(2026, 3, 7)
        # B: start = 2026-03-07, end = 2026-03-09 (+3 days)
        assert tasks["B"].start_date == date(2026, 3, 7)
        assert tasks["B"].end_date == date(2026, 3, 9)
        # C: start = 2026-03-07, end = 2026-03-11 (+3 days)
        assert tasks["C"].start_date == date(2026, 3, 7)
        assert tasks["C"].end_date == date(2026, 3, 11)
        # D: start = max(end(B)=03-09, end(C)=03-11) = 2026-03-11. end = 2026-03-13.
        # Original end date was 2026-03-10.
        # 2026-03-13 - 2026-03-10 = EXACTLY 3 DAYS! Not 6 days!
        assert tasks["D"].start_date == date(2026, 3, 11)
        assert tasks["D"].end_date == date(2026, 3, 13)

    def test_multi_level_transitive_propagation(self):
        # A -> B -> C -> D -> E
        base_date = date(2026, 4, 1)
        tasks = {
            "A": create_sample_task("A", "Task A", duration_days=2, planned_start=base_date),
            "B": create_sample_task("B", "Task B", duration_days=3, planned_start=base_date),
            "C": create_sample_task("C", "Task C", duration_days=1, planned_start=base_date),
            "D": create_sample_task("D", "Task D", duration_days=4, planned_start=base_date),
            "E": create_sample_task("E", "Task E", duration_days=2, planned_start=base_date),
        }
        edges = [
            DependencyEdge(task_id="B", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="B"),
            DependencyEdge(task_id="D", prerequisite_id="C"),
            DependencyEdge(task_id="E", prerequisite_id="D"),
        ]

        DAGEngine.recompute_schedule(tasks, edges)
        # A: 04-01 -> 04-03
        # B: 04-03 -> 04-06
        # C: 04-06 -> 04-07
        # D: 04-07 -> 04-11
        # E: 04-11 -> 04-13
        assert tasks["E"].end_date == date(2026, 4, 13)

        # Slip A by 5 days
        tasks["A"].duration_days = 7
        DAGEngine.recompute_schedule(tasks, edges, changed_task_ids=["A"])
        # E should be shifted by exactly 5 days to 2026-04-18
        assert tasks["E"].end_date == date(2026, 4, 18)


class TestBlockedReadyAndRollback:
    def test_blocked_vs_ready_initial(self):
        tasks = {
            "A": create_sample_task("A", "Prereq 1", column=TaskColumn.BACKLOG),
            "B": create_sample_task("B", "Prereq 2", column=TaskColumn.DONE),
            "C": create_sample_task("C", "Dependent", column=TaskColumn.BACKLOG),
        }
        edges = [
            DependencyEdge(task_id="C", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="B"),
        ]

        DAGEngine.recompute_schedule(tasks, edges)
        # A has no prereqs -> Ready
        assert not tasks["A"].is_blocked
        # B has no prereqs and is done -> Ready
        assert not tasks["B"].is_blocked
        # C has A (Backlog) and B (Done) -> Blocked because A is not Done
        assert tasks["C"].is_blocked
        assert tasks["C"].blocking_task_ids == ["A"]

        # Mark A as Done -> C becomes Ready
        tasks["A"].column = TaskColumn.DONE
        DAGEngine.recompute_schedule(tasks, edges)
        assert not tasks["C"].is_blocked
        assert tasks["C"].blocking_task_ids == []

    def test_rollback_reblocks_dependents_and_warns(self):
        """
        Moving a Done task back to In Progress must re-block its dependents.
        On regression, downstream tasks already In Progress/Review keep their column
        but are flagged Blocked with a warning.
        """
        tasks = {
            "A": create_sample_task("A", "Prereq", column=TaskColumn.DONE),
            "B": create_sample_task("B", "Dependent 1", column=TaskColumn.IN_PROGRESS),
            "C": create_sample_task("C", "Dependent 2", column=TaskColumn.BACKLOG),
        }
        edges = [
            DependencyEdge(task_id="B", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="B"),
        ]

        # Prior state: A is Done, B is In Progress (valid), C is Blocked (because B is In Progress)
        DAGEngine.recompute_schedule(tasks, edges)
        assert not tasks["B"].is_blocked
        assert not tasks["B"].has_regression_warning
        assert tasks["C"].is_blocked

        # Now Task A regresses to IN_PROGRESS
        tasks["A"].column = TaskColumn.IN_PROGRESS
        DAGEngine.recompute_schedule(tasks, edges, changed_task_ids=["A"])

        # B is now Blocked because A is no longer Done
        assert tasks["B"].is_blocked
        # And because B is in IN_PROGRESS, it must have a regression warning!
        assert tasks["B"].has_regression_warning
        assert "unfinished prerequisite" in (tasks["B"].warning_message or "")
        # C is also still blocked
        assert tasks["C"].is_blocked

    def test_blocked_task_cannot_move_forward(self):
        blocked_task = create_sample_task("T", "Blocked Task", column=TaskColumn.BACKLOG)
        blocked_task.is_blocked = True
        blocked_task.blocking_task_ids = ["P1"]

        # Should fail for IN_PROGRESS, REVIEW, DONE
        valid_ip, msg_ip = DAGEngine.validate_move(blocked_task, TaskColumn.IN_PROGRESS)
        assert not valid_ip
        assert "Cannot move Blocked task" in (msg_ip or "")

        valid_done, msg_done = DAGEngine.validate_move(blocked_task, TaskColumn.DONE)
        assert not valid_done

        # Should be permitted to stay in BACKLOG
        valid_backlog, _ = DAGEngine.validate_move(blocked_task, TaskColumn.BACKLOG)
        assert valid_backlog


class TestCriticalPath:
    def test_critical_path_calculation(self):
        """
        Path 1: A (3) -> B (2) -> D (2) = total 7 days
        Path 2: A (3) -> C (4) -> D (2) = total 9 days
        Critical path must be [A, C, D]
        """
        tasks = {
            "A": create_sample_task("A", "Task A", duration_days=3),
            "B": create_sample_task("B", "Task B", duration_days=2),
            "C": create_sample_task("C", "Task C", duration_days=4),
            "D": create_sample_task("D", "Task D", duration_days=2),
        }
        edges = [
            DependencyEdge(task_id="B", prerequisite_id="A"),
            DependencyEdge(task_id="C", prerequisite_id="A"),
            DependencyEdge(task_id="D", prerequisite_id="B"),
            DependencyEdge(task_id="D", prerequisite_id="C"),
        ]

        res = DAGEngine.recompute_schedule(tasks, edges)
        assert res.critical_path == ["A", "C", "D"]
        assert tasks["A"].is_critical_path
        assert tasks["C"].is_critical_path
        assert tasks["D"].is_critical_path
        assert not tasks["B"].is_critical_path
