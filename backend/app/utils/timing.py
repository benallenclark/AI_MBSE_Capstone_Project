import time

def now_ns() -> int:
    return time.perf_counter_ns()

def ms_since(t0_ns: int) -> float:
    # precise ms as float
    return (time.perf_counter_ns() - t0_ns) / 1_000_000.0
