"""Read process identity and HWND ownership without modifying the desktop."""
import ctypes as c
from ctypes import wintypes as w

from app_launch import Running
from windows_tray import bind


class WindowsInstances:
    def __init__(self, user, kernel):
        self.user, self.kernel = user, kernel
        self.aumid = bind(kernel, "GetApplicationUserModelId",
                          [w.HANDLE, c.POINTER(w.UINT), w.LPWSTR], w.LONG)
        self.times = bind(kernel, "GetProcessTimes", [w.HANDLE, *([c.POINTER(w.FILETIME)] * 4)], w.BOOL)
        self.processes = bind(kernel, "K32EnumProcesses",
                              [c.POINTER(w.DWORD), w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        self.child_callback = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        self.children = bind(user, "EnumChildWindows", [w.HWND, self.child_callback, w.LPARAM], w.BOOL)

    def read(self, pid):
        process = self.kernel.OpenProcess(0x1000, False, pid) if pid else None
        if not process:
            return Running(pid, "")
        try:
            path = c.create_unicode_buffer(32768)
            size = w.DWORD(len(path))
            app = c.create_unicode_buffer(256)
            count = w.UINT(len(app))
            times = [w.FILETIME() for _ in range(4)]
            read = self.kernel.QueryFullProcessImageNameW(process, 0, path, c.byref(size))
            appid = app.value if self.aumid(process, c.byref(count), app) == 0 else ""
            started = 0
            if self.times(process, *(c.byref(item) for item in times)):
                started = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return Running(pid, path.value if read else "", appid, 0, started)
        finally:
            self.kernel.CloseHandle(process)

    def owner(self, handle):
        pid = w.DWORD()
        self.user.GetWindowThreadProcessId(handle, c.byref(pid))
        return pid.value

    def window(self, handle, read):
        owner = read(self.owner(handle))
        if owner.executable.casefold().endswith(r"\applicationframehost.exe"):
            found = []

            @self.child_callback
            def collect(child, _unused):
                pid = self.owner(child)
                if pid != owner.pid:
                    process = read(pid)
                    if process.aumid:
                        found.append(process)
                        return False
                return True

            self.children(handle, collect, 0)
            if found:
                owner = found[0]
        return Running(owner.pid, owner.executable, owner.aumid, handle, owner.started)

    def all(self):
        size = 512
        while size <= 16384:
            pids = (w.DWORD * size)()
            written = w.DWORD()
            if not self.processes(pids, c.sizeof(pids), c.byref(written)):
                return ()
            count = written.value // c.sizeof(w.DWORD)
            if count < size or size == 16384:
                return (self.read(pid) for pid in pids[:count] if pid)
            size *= 2
        return ()
