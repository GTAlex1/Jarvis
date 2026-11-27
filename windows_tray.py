"""Native Windows notification icon, desktop messages and single-instance guard."""
import ctypes as c
from ctypes import wintypes as w
from contextlib import contextmanager
import time

# The suffix distinguishes this project's objects from other apps named JARVIS.
WINDOW_CLASS = "GTAlex1.Jarvis.Resident.57D0676F"
MUTEX_NAME = "Local\\" + WINDOW_CLASS
OPEN_MESSAGE = WINDOW_CLASS + ".Open"
WM_TRAY = 0x8001  # WM_APP + 1
WM_NULL = 0
WM_HOTKEY = 0x0312
WM_CONTEXTMENU = 0x007B
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
NIN_SELECT = 0x0400
NIN_KEYSELECT = 0x0401
NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETVERSION = 0, 1, 2, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_SHOWTIP = 1, 2, 4, 0x80
ERROR_ALREADY_EXISTS = 183
MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008


class GUID(c.Structure):
    _fields_ = [("data1", w.DWORD), ("data2", w.WORD), ("data3", w.WORD), ("data4", w.BYTE * 8)]


class NotifyIconData(c.Structure):
    _fields_ = [
        ("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT),
        ("uCallbackMessage", w.UINT), ("hIcon", w.HICON), ("szTip", w.WCHAR * 128),
        ("dwState", w.DWORD), ("dwStateMask", w.DWORD), ("szInfo", w.WCHAR * 256),
        ("uVersion", w.UINT), ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
        ("guidItem", GUID), ("hBalloonIcon", w.HICON),
    ]


def bind(library, name, args, result):
    function = getattr(library, name)
    function.argtypes = args
    function.restype = result
    return function


@contextmanager
def single_instance():
    kernel = c.WinDLL("kernel32", use_last_error=True)
    create = bind(kernel, "CreateMutexW", [w.LPVOID, w.BOOL, w.LPCWSTR], w.HANDLE)
    close = bind(kernel, "CloseHandle", [w.HANDLE], w.BOOL)
    c.set_last_error(0)
    handle = create(None, False, MUTEX_NAME)
    error = c.get_last_error()
    if not handle:
        raise c.WinError(error)
    first = error != ERROR_ALREADY_EXISTS
    if not first:
        close(handle)
        handle = None
    try:
        yield first
    finally:
        if handle:
            close(handle)


def show_running_instance():
    user = c.WinDLL("user32", use_last_error=True)
    register = bind(user, "RegisterWindowMessageW", [w.LPCWSTR], w.UINT)
    find = bind(user, "FindWindowW", [w.LPCWSTR, w.LPCWSTR], w.HWND)
    notify = bind(user, "PostMessageW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL)
    message = register(OPEN_MESSAGE)
    if message:
        # Another copy may have acquired the mutex just before creating its window.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            window = find(WINDOW_CLASS, None)
            if window and notify(window, message, 0, 0):
                return True
            time.sleep(0.05)
    return False


class WindowsTray:
    def __init__(self, root, show, menu_items, run_action, defer):
        self.root = root
        self.show = show
        self.menu_items = menu_items
        self.run_action = run_action
        self.defer = defer
        self.retry = None
        self.visible = False
        self.tooltip = "JARVIS"
        self.version4 = False
        self.hotkey = None
        self.hotkey_id = 1000
        self.window = None

        user = c.WinDLL("user32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        shell = c.WinDLL("shell32", use_last_error=True)
        self.notify = bind(shell, "Shell_NotifyIconW", [w.DWORD, c.POINTER(NotifyIconData)], w.BOOL)
        result = c.c_ssize_t
        wndproc = c.WINFUNCTYPE(result, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        class WindowClass(c.Structure):
            _fields_ = [
                ("style", w.UINT), ("proc", wndproc), ("class_extra", c.c_int),
                ("window_extra", c.c_int), ("instance", w.HINSTANCE), ("icon", w.HICON),
                ("cursor", w.HANDLE), ("background", w.HBRUSH), ("menu_name", w.LPCWSTR),
                ("class_name", w.LPCWSTR),
            ]

        functions = {
            "RegisterHotKey": ([w.HWND, c.c_int, w.UINT, w.UINT], w.BOOL),
            "UnregisterHotKey": ([w.HWND, c.c_int], w.BOOL),
            "RegisterWindowMessageW": ([w.LPCWSTR], w.UINT),
            "RegisterClassW": ([c.POINTER(WindowClass)], w.ATOM),
            "UnregisterClassW": ([w.LPCWSTR, w.HINSTANCE], w.BOOL),
            "CreateWindowExW": ([
                w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int, c.c_int, c.c_int, c.c_int,
                w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID,
            ], w.HWND),
            "DestroyWindow": ([w.HWND], w.BOOL),
            "DefWindowProcW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], result),
            "PostMessageW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
            "LoadIconW": ([w.HINSTANCE, c.c_void_p], w.HICON),
            "CreatePopupMenu": ([], w.HMENU),
            "AppendMenuW": ([w.HMENU, w.UINT, c.c_size_t, w.LPCWSTR], w.BOOL),
            "DestroyMenu": ([w.HMENU], w.BOOL),
            "TrackPopupMenu": ([w.HMENU, w.UINT, c.c_int, c.c_int, c.c_int, w.HWND, w.LPVOID], w.UINT),
            "GetCursorPos": ([c.POINTER(w.POINT)], w.BOOL),
            "SetForegroundWindow": ([w.HWND], w.BOOL),
        }
        for name, (args, restype) in functions.items():
            bind(user, name, args, restype)
        self.user = user
        self.instance = bind(kernel, "GetModuleHandleW", [w.LPCWSTR], w.HMODULE)(None)
        self.taskbar_created = user.RegisterWindowMessageW("TaskbarCreated")
        self.open_message = user.RegisterWindowMessageW(OPEN_MESSAGE)
        self.icon = user.LoadIconW(None, 32512)  # Shared IDI_APPLICATION icon.
        if not all((self.instance, self.taskbar_created, self.open_message, self.icon)):
            raise c.WinError(c.get_last_error())
        self.proc = wndproc(self.window_proc)
        definition = WindowClass(proc=self.proc, instance=self.instance, class_name=WINDOW_CLASS)
        if not user.RegisterClassW(c.byref(definition)):
            raise c.WinError(c.get_last_error())
        # A hidden top-level window receives Explorer's TaskbarCreated broadcast.
        self.window = user.CreateWindowExW(
            0, WINDOW_CLASS, "", 0, 0, 0, 0, 0, None, None, self.instance, None,
        )
        if not self.window:
            error = c.get_last_error()
            user.UnregisterClassW(WINDOW_CLASS, self.instance)
            raise c.WinError(error)

    def notify_data(self):
        data = NotifyIconData()
        data.cbSize = c.sizeof(data)
        data.hWnd = self.window
        data.uID = 1
        return data

    def add_icon(self, retries=6):
        self.retry = None
        data = self.notify_data()
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self.icon
        data.szTip = self.tooltip
        self.visible = bool(self.notify(NIM_ADD, c.byref(data)) or
                            self.notify(NIM_MODIFY, c.byref(data)))
        if self.visible:
            data.uVersion = 4  # Enable keyboard selection and WM_CONTEXTMENU.
            self.version4 = bool(self.notify(NIM_SETVERSION, c.byref(data)))
        elif retries:
            self.retry = self.root.after(1500, self.add_icon, retries - 1)
        return self.visible

    def set_tooltip(self, text):
        self.tooltip = text[:127]
        if self.visible:
            data = self.notify_data()
            data.uFlags = NIF_TIP | NIF_SHOWTIP
            data.szTip = self.tooltip
            self.notify(NIM_MODIFY, c.byref(data))

    def restore_icon(self):
        if self.retry is not None:
            self.root.after_cancel(self.retry)
        self.add_icon()

    def window_proc(self, window, message, wp, lp):
        # Tk may be inside its native event dispatcher here. Queue Python
        # callbacks and let the resident call Tk once the dispatch is over.
        if message == self.open_message:
            self.defer(self.show)
        elif message == self.taskbar_created:
            self.defer(self.restore_icon)
        elif message == WM_HOTKEY:
            if self.hotkey is not None and wp == self.hotkey_id:
                self.defer(self.hotkey)
        elif message == WM_TRAY:
            event = lp & 0xFFFF
            if event in (NIN_SELECT, NIN_KEYSELECT, WM_LBUTTONDBLCLK):
                self.defer(self.show)
            elif event == WM_CONTEXTMENU and self.version4:
                point = c.c_short(wp & 0xFFFF).value, c.c_short((wp >> 16) & 0xFFFF).value
                self.defer(self.popup, point)
            elif event == WM_RBUTTONUP and not self.version4:
                self.defer(self.popup, (-1, -1))
        else:
            return self.user.DefWindowProcW(window, message, wp, lp)
        return 0

    def popup(self, point):
        menu = self.user.CreatePopupMenu()
        if not menu:
            return
        try:
            items = self.menu_items()
            for index, item in enumerate(items, 1):
                if item is None:
                    self.user.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                else:
                    label, checked, _ = item
                    self.user.AppendMenuW(menu, MF_CHECKED if checked else 0, index, label)
            if point == (-1, -1):
                cursor = w.POINT()
                self.user.GetCursorPos(c.byref(cursor))
                point = (cursor.x, cursor.y)
            self.user.SetForegroundWindow(self.window)
            # TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON
            selected = self.user.TrackPopupMenu(menu, 0x0182, *point, 0, self.window, None)
            self.user.PostMessageW(self.window, WM_NULL, 0, 0)
            if selected:
                self.run_action(items[selected - 1][2])
        finally:
            self.user.DestroyMenu(menu)

    def set_hotkey(self, callback):
        self.clear_hotkey()
        self.hotkey_id = 1000 + (self.hotkey_id - 999) % 30000
        if not self.user.RegisterHotKey(self.window, self.hotkey_id, 0x4003, 0x79):  # Ctrl+Alt+F10
            return False
        self.hotkey = callback
        return True

    def clear_hotkey(self):
        if self.hotkey is not None:
            self.user.UnregisterHotKey(self.window, self.hotkey_id)
            self.hotkey = None

    def close(self):
        self.clear_hotkey()
        if self.retry is not None:
            self.root.after_cancel(self.retry)
        data = self.notify_data()
        if self.visible:
            self.notify(NIM_DELETE, c.byref(data))
        self.user.DestroyWindow(self.window)
        self.user.UnregisterClassW(WINDOW_CLASS, self.instance)
        self.window = None
