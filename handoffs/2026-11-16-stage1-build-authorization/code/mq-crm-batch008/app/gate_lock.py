"""Privacy-gate lock (Batch 008).

Closes Batch 006 declared gap 2 (withdrawal vs in-flight dispatch). A
dispatch holds the lock SHARED from its final gate re-check until its
transport call returns; changing a register row's review state takes it
EXCLUSIVE. So every dispatch is linearized entirely before or entirely
after a withdrawal:
- a dispatch that has not reached its pre-send re-check when the
  withdrawal commits is refused (nothing leaves);
- a withdrawal requested while a POST is already on the wire waits for that
  POST to finish (bounded by the 5 s transport timeout) and only then
  commits — it can never commit while a payload it forbids is leaving.
Scope, stated: this is an in-process lock. Stage 1 is a single-process
app; a multi-process deployment needs a DB- or broker-level lease.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager


class _RWLock:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._readers = 0
        self._writer = False
        self._writers_waiting = 0

    @contextmanager
    def shared(self):
        with self._cond:
            while self._writer or self._writers_waiting:
                self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._cond:
                self._readers -= 1
                self._cond.notify_all()

    @contextmanager
    def exclusive(self):
        with self._cond:
            self._writers_waiting += 1
            try:
                while self._writer or self._readers:
                    self._cond.wait()
            finally:
                self._writers_waiting -= 1
            self._writer = True
        try:
            yield
        finally:
            with self._cond:
                self._writer = False
                self._cond.notify_all()


GATE_LOCK = _RWLock()
