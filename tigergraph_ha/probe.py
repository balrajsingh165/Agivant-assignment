"""In-process availability probe and recovery-metric analysis."""
import threading
import time
import urllib.request


class Probe:
    """Sample an HTTP endpoint on a background thread at a fixed interval."""

    def __init__(self, url, interval=0.25, timeout=3.0):
        self.url = url
        self.interval = interval
        self.timeout = timeout
        self.samples = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _once(self):
        try:
            with urllib.request.urlopen(self.url, timeout=self.timeout) as r:
                return 200 <= r.status < 300
        except Exception:
            return False

    def _loop(self):
        while not self._stop.is_set():
            self.samples.append((time.time(), self._once()))
            self._stop.wait(self.interval)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)


def analyze(samples, fault_ts):
    """Derive availability, outage windows, MTTD and MTTR from probe samples.

    MTTD is the time from fault injection to the first failed request; MTTR is the
    time from fault injection to sustained recovery (end of the outage window).
    """
    total = len(samples)
    ok = sum(1 for _, o in samples if o)
    windows, start = [], None
    for ts, o in samples:
        if not o and start is None:
            start = ts
        elif o and start is not None:
            windows.append((start, ts))
            start = None
    if start is not None:
        windows.append((start, samples[-1][0]))

    res = {
        "total": total,
        "ok": ok,
        "failed": total - ok,
        "availability_pct": round(100 * ok / total, 2) if total else 0.0,
        "outages": [{"start": round(s, 3), "end": round(e, 3), "seconds": round(e - s, 2)} for s, e in windows],
        "downtime_s": round(sum(e - s for s, e in windows), 2),
        "mttd_s": None,
        "mttr_s": None,
    }
    after = [(s, e) for s, e in windows if e >= fault_ts]
    if after:
        res["mttd_s"] = round(after[0][0] - fault_ts, 2)   # first failure after the fault
        res["mttr_s"] = round(after[-1][1] - fault_ts, 2)  # sustained recovery (last window ends)
    return res
