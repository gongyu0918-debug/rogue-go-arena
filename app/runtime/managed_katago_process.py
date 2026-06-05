from __future__ import annotations

import ctypes
import subprocess
import sys
from dataclasses import dataclass
from ctypes import wintypes
from typing import Any, Callable, Optional


LogFn = Callable[[str], None]


class _IOCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9


class _WindowsKataGoJob:
    def __init__(self, *, log_fn: LogFn | None = None) -> None:
        self._log_fn = log_fn
        self._handle: Optional[int] = None

    def assign(self, process: subprocess.Popen[Any]) -> None:
        if sys.platform != "win32":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            self._log_windows_error("CreateJobObjectW failed")
            return

        limits = _JobObjectExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        if not ok:
            self._log_windows_error("SetInformationJobObject failed")
            kernel32.CloseHandle(handle)
            return

        process_handle = getattr(process, "_handle", None)
        if not process_handle:
            kernel32.CloseHandle(handle)
            return

        if not kernel32.AssignProcessToJobObject(handle, process_handle):
            self._log_windows_error("AssignProcessToJobObject failed")
            kernel32.CloseHandle(handle)
            return

        self._handle = int(handle)

    def close(self) -> None:
        if sys.platform != "win32" or not self._handle:
            self._handle = None
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle(wintypes.HANDLE(self._handle))
        self._handle = None

    def _log_windows_error(self, prefix: str) -> None:
        if not self._log_fn:
            return
        err = ctypes.get_last_error()
        self._log_fn(f"[KataGo] {prefix}: Windows error {err}")


@dataclass
class ManagedKataGoProcess:
    process: subprocess.Popen[Any]
    _job: _WindowsKataGoJob | None = None

    @classmethod
    def start(
        cls,
        cmd: list[str],
        *,
        log_fn: LogFn | None = None,
        **popen_kwargs: Any,
    ) -> "ManagedKataGoProcess":
        process = subprocess.Popen(cmd, **popen_kwargs)
        job: _WindowsKataGoJob | None = None
        if sys.platform == "win32":
            job = _WindowsKataGoJob(log_fn=log_fn)
            job.assign(process)
        return cls(process=process, _job=job)

    def terminate_tree(self, *, timeout: float = 5.0) -> None:
        try:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=timeout)
        except Exception:
            try:
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass
        finally:
            self.close_job()

    def close_job(self) -> None:
        if self._job:
            self._job.close()
            self._job = None
