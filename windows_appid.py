"""Read the explicit AppUserModelID of a Windows top-level window."""
import ctypes as c
from ctypes import wintypes as w
from uuid import UUID

from windows_tray import bind


class GUID(c.Structure):
    _fields_ = [("data", c.c_ubyte * 16)]


class PropertyKey(c.Structure):
    _fields_ = [("format", GUID), ("id", c.c_uint32)]


class PropertyValue(c.Structure):
    # The largest union member is a vector (count plus pointer).
    _fields_ = [("type", w.WORD), ("reserved", w.WORD * 3), ("payload", c.c_void_p * 2)]


IID_PROPERTY_STORE = GUID.from_buffer_copy(UUID("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99").bytes_le)
APP_ID = PropertyKey(GUID.from_buffer_copy(UUID("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3").bytes_le), 5)


class WindowAppId:
    def __init__(self):
        shell = c.WinDLL("shell32")
        ole = c.WinDLL("ole32")
        self.open = bind(shell, "SHGetPropertyStoreForWindow",
                         [w.HWND, c.POINTER(GUID), c.POINTER(c.c_void_p)], w.LONG)
        self.init = bind(ole, "CoInitializeEx", [c.c_void_p, w.DWORD], w.LONG)
        self.uninit = bind(ole, "CoUninitialize", [], None)
        self.clear = bind(ole, "PropVariantClear", [c.POINTER(PropertyValue)], w.LONG)
        self.get_value = c.WINFUNCTYPE(w.LONG, c.c_void_p, c.POINTER(PropertyKey), c.POINTER(PropertyValue))
        self.release = c.WINFUNCTYPE(w.ULONG, c.c_void_p)

    def __call__(self, window):
        status = self.init(None, 2)
        if status < 0 and status != -2147417850:  # Existing COM apartment may use another threading model.
            return ""
        store = c.c_void_p()
        try:
            if self.open(window, c.byref(IID_PROPERTY_STORE), c.byref(store)) < 0 or not store:
                return ""
            methods = c.cast(store, c.POINTER(c.POINTER(c.c_void_p))).contents
            try:
                value = PropertyValue()
                if self.get_value(methods[5])(store, c.byref(APP_ID), c.byref(value)) < 0:
                    return ""
                try:
                    return c.wstring_at(value.payload[0]) if value.type == 31 and value.payload[0] else ""
                finally:
                    self.clear(c.byref(value))
            finally:
                self.release(methods[2])(store)
        finally:
            if status >= 0:
                self.uninit()
