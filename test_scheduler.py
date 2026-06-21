"""
test_scheduler.py - Correctness checks for the scheduling engine.

Each test uses a small example whose answer can be worked out by hand (several
are the classic textbook examples), so we can be confident the algorithms are
implemented correctly. Run it with:

    python test_scheduler.py
"""
import math

from scheduler import (
    Process, fcfs, sjf, srtf, round_robin,
    priority_scheduling, priority_preemptive, IDLE_LABEL,
    run_algorithm, compare_all,
)


def approx(a, b, tol=1e-9):
    return math.isclose(a, b, abs_tol=tol)


def metrics_by_pid(result):
    return {m.pid: m for m in result.metrics}


def test_fcfs():
    procs = [
        Process("P1", arrival=0, burst=4),
        Process("P2", arrival=1, burst=3),
        Process("P3", arrival=2, burst=1),
    ]
    r = fcfs(procs)
    m = metrics_by_pid(r)
    assert (m["P1"].completion, m["P2"].completion, m["P3"].completion) == (4, 7, 8)
    assert (m["P1"].waiting, m["P2"].waiting, m["P3"].waiting) == (0, 3, 5)
    assert approx(r.avg_waiting, 8 / 3)
    assert approx(r.avg_turnaround, 16 / 3)
    assert r.gantt == [("P1", 0, 4), ("P2", 4, 7), ("P3", 7, 8)]
    print("FCFS                  OK   avg wait = %.3f" % r.avg_waiting)


def test_fcfs_with_idle_gap():
    # The CPU should sit idle from t=0..2 before P1 arrives.
    procs = [Process("P1", arrival=2, burst=2), Process("P2", arrival=5, burst=2)]
    r = fcfs(procs)
    assert r.gantt[0] == (IDLE_LABEL, 0, 2)
    assert r.gantt[2] == (IDLE_LABEL, 4, 5)  # idle again until P2 arrives
    assert approx(r.cpu_utilization, 4 / 7 * 100)
    print("FCFS (idle handling)  OK   cpu util = %.1f%%" % r.cpu_utilization)


def test_sjf():
    procs = [
        Process("P1", arrival=0, burst=4),
        Process("P2", arrival=1, burst=3),
        Process("P3", arrival=2, burst=1),
    ]
    r = sjf(procs)
    m = metrics_by_pid(r)
    # At t=4 both P2 and P3 are ready; the shorter P3 runs first.
    assert r.gantt == [("P1", 0, 4), ("P3", 4, 5), ("P2", 5, 8)]
    assert (m["P1"].waiting, m["P2"].waiting, m["P3"].waiting) == (0, 4, 2)
    assert approx(r.avg_waiting, 2.0)
    print("SJF                   OK   avg wait = %.3f" % r.avg_waiting)


def test_srtf():
    # Classic Silberschatz example; the known answer is avg waiting = 6.5.
    procs = [
        Process("P1", arrival=0, burst=8),
        Process("P2", arrival=1, burst=4),
        Process("P3", arrival=2, burst=9),
        Process("P4", arrival=3, burst=5),
    ]
    r = srtf(procs)
    m = metrics_by_pid(r)
    assert (m["P1"].completion, m["P2"].completion,
            m["P3"].completion, m["P4"].completion) == (17, 5, 26, 10)
    assert approx(r.avg_waiting, 6.5)
    assert approx(r.avg_turnaround, 13.0)
    print("SRTF                  OK   avg wait = %.3f" % r.avg_waiting)


def test_round_robin():
    # Classic example: three jobs all arriving at 0 with quantum 4.
    procs = [
        Process("P1", arrival=0, burst=24),
        Process("P2", arrival=0, burst=3),
        Process("P3", arrival=0, burst=3),
    ]
    r = round_robin(procs, quantum=4)
    m = metrics_by_pid(r)
    assert (m["P1"].completion, m["P2"].completion, m["P3"].completion) == (30, 7, 10)
    assert (m["P1"].waiting, m["P2"].waiting, m["P3"].waiting) == (6, 4, 7)
    assert approx(r.avg_waiting, 17 / 3)
    # Response time matters for RR: P3 waits for two slices before first run.
    assert m["P3"].response == 7
    print("Round Robin           OK   avg wait = %.3f" % r.avg_waiting)


def test_round_robin_with_arrivals():
    # Verifies the "new arrivals queue before the preempted process" rule.
    procs = [
        Process("P1", arrival=0, burst=5),
        Process("P2", arrival=1, burst=4),
        Process("P3", arrival=2, burst=2),
    ]
    r = round_robin(procs, quantum=2)
    # Expected order: P1[0-2] P2[2-4] P3[4-6] P1[6-8] P2[8-10] P1[10-11]
    assert r.gantt == [
        ("P1", 0, 2), ("P2", 2, 4), ("P3", 4, 6),
        ("P1", 6, 8), ("P2", 8, 10), ("P1", 10, 11),
    ]
    m = metrics_by_pid(r)
    assert m["P1"].completion == 11
    assert m["P2"].completion == 10
    assert m["P3"].completion == 6
    print("Round Robin (arrivals)OK   avg wait = %.3f" % r.avg_waiting)


def test_priority_non_preemptive():
    # Classic example, all arriving at 0; known avg waiting = 8.2.
    procs = [
        Process("P1", arrival=0, burst=10, priority=3),
        Process("P2", arrival=0, burst=1, priority=1),
        Process("P3", arrival=0, burst=2, priority=4),
        Process("P4", arrival=0, burst=1, priority=5),
        Process("P5", arrival=0, burst=5, priority=2),
    ]
    r = priority_scheduling(procs)
    assert r.execution_order == ["P2", "P5", "P1", "P3", "P4"]
    assert approx(r.avg_waiting, 8.2)
    assert approx(r.avg_turnaround, 12.0)
    print("Priority (non-preempt)OK   avg wait = %.3f" % r.avg_waiting)


def test_priority_preemptive():
    procs = [
        Process("P1", arrival=0, burst=4, priority=3),
        Process("P2", arrival=1, burst=3, priority=1),  # preempts P1 at t=1
        Process("P3", arrival=2, burst=1, priority=2),
    ]
    r = priority_preemptive(procs)
    # P1[0-1] P2[1-4] (highest prio) P3[4-5] P1[5-8]
    assert r.gantt == [("P1", 0, 1), ("P2", 1, 4), ("P3", 4, 5), ("P1", 5, 8)]
    m = metrics_by_pid(r)
    assert m["P1"].completion == 8 and m["P2"].completion == 4
    print("Priority (preemptive) OK   avg wait = %.3f" % r.avg_waiting)


def test_single_process():
    r = fcfs([Process("P1", arrival=3, burst=5)])
    m = metrics_by_pid(r)
    assert m["P1"].waiting == 0 and m["P1"].turnaround == 5
    assert m["P1"].completion == 8 and m["P1"].response == 0
    print("Single process        OK")


def test_validation():
    for bad in (
        lambda: Process("P1", arrival=-1, burst=2),
        lambda: Process("P1", arrival=0, burst=0),
    ):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for invalid process")

    try:
        fcfs([])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty process list")

    try:
        fcfs([Process("P1", 0, 2), Process("P1", 0, 3)])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for duplicate pids")
    print("Validation            OK")

def test_run_algorithm_dispatch():
    procs = [Process("P1", arrival=0, burst=4), Process("P2", arrival=1, burst=3)]
    # Non-RR algorithms should match calling the function directly.
    direct = fcfs(procs)
    via_dispatch = run_algorithm("FCFS", procs)
    assert via_dispatch.gantt == direct.gantt
    # Round Robin must receive the quantum.
    rr_direct = round_robin(procs, quantum=2)
    rr_dispatch = run_algorithm("Round Robin", procs, quantum=2)
    assert rr_dispatch.gantt == rr_direct.gantt
    assert rr_dispatch.quantum == 2
    # Unknown algorithm name must raise.
    try:
        run_algorithm("Not A Real Algorithm", procs)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown algorithm name")
    print("run_algorithm dispatch OK")


def test_compare_all():
    procs = [Process("P1", arrival=0, burst=4), Process("P2", arrival=1, burst=3)]
    results = compare_all(procs, quantum=2)
    # One result per registered algorithm, in ALGORITHMS order.
    assert len(results) == 6
    names = [r.algorithm for r in results]
    assert names == [
        "FCFS", "SJF (Non-preemptive)", "SRTF (Preemptive SJF)",
        "Round Robin", "Priority (Non-preemptive)", "Priority (Preemptive)",
    ]
    # The Round Robin result should have used the quantum we passed in.
    rr = next(r for r in results if r.algorithm == "Round Robin")
    assert rr.quantum == 2
    print("compare_all            OK   %d algorithms" % len(results))


def test_round_robin_idle_gap():
    # P1 arrives at 0, finishes its only slice; P2 doesn't arrive until t=5,
    # so the CPU must sit idle from t=2 to t=5.
    procs = [Process("P1", arrival=0, burst=2), Process("P2", arrival=5, burst=2)]
    r = round_robin(procs, quantum=4)
    assert r.gantt == [("P1", 0, 2), (IDLE_LABEL, 2, 5), ("P2", 5, 7)]
    m = metrics_by_pid(r)
    assert m["P1"].waiting == 0
    assert m["P2"].waiting == 0  # P2 ran immediately on arrival
    print("Round Robin (idle gap) OK")


def test_priority_preemptive_idle_gap():
    # Nothing is ready from t=0..3; P1 arrives at 3.
    procs = [Process("P1", arrival=3, burst=4, priority=1),
             Process("P2", arrival=10, burst=2, priority=1)]
    r = priority_preemptive(procs)
    assert r.gantt[0] == (IDLE_LABEL, 0, 3)
    m = metrics_by_pid(r)
    assert m["P1"].completion == 7
    assert m["P1"].waiting == 0
    # Idle gap again between P1 finishing (7) and P2 arriving (10).
    assert (IDLE_LABEL, 7, 10) in r.gantt
    print("Priority-preempt (idle)OK")


def main():
    tests = [
        test_fcfs,
        test_fcfs_with_idle_gap,
        test_sjf,
        test_srtf,
        test_round_robin,
        test_round_robin_with_arrivals,
        test_round_robin_idle_gap,
        test_priority_non_preemptive,
        test_priority_preemptive,
        test_priority_preemptive_idle_gap,
        test_single_process,
        test_validation,
        test_run_algorithm_dispatch,
        test_compare_all,
    ]
    print("Running scheduling engine tests\n" + "-" * 40)
    for t in tests:
        t()
    print("-" * 40)
    print("All %d tests passed." % len(tests))


if __name__ == "__main__":
    main()
