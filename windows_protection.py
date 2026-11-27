"""Windows current-user DPAPI storage for voice profiles."""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from speakers import decode_profiles, encode_profiles

MAX_FILE = 512 * 1024


class DataBlob(c.Structure):
    _fields_ = [("size", w.DWORD), ("data", c.POINTER(c.c_ubyte))]


def dpapi(data, protect):
    buffer = (c.c_ubyte * len(data)).from_buffer_copy(data)
    value = DataBlob(len(data), buffer)
    result = DataBlob()
    crypt = c.WinDLL("crypt32", use_last_error=True)
    function = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    function.argtypes = [c.POINTER(DataBlob), w.LPCWSTR if protect else c.c_void_p,
                         c.c_void_p, c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(DataBlob)]
    function.restype = w.BOOL
    if not function(c.byref(value), None, None, None, None, 1, c.byref(result)):  # UI forbidden
        raise c.WinError(c.get_last_error())
    try:
        return c.string_at(result.data, result.size)
    finally:
        free = c.windll.kernel32.LocalFree
        free.argtypes = [c.c_void_p]
        free.restype = c.c_void_p
        free(result.data)
        c.memset(buffer, 0, len(buffer))


class ProfileStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ["LOCALAPPDATA"]) / "JARVIS" / "perfiles-voz.dat"

    def load(self):
        try:
            with self.path.open("rb") as source:
                data = source.read(MAX_FILE + 1)
        except FileNotFoundError:
            return ()
        if len(data) > MAX_FILE:
            raise ValueError("El archivo de perfiles excede el tamaño esperado.")
        return decode_profiles(dpapi(data, False))

    def save(self, profiles):
        data = dpapi(encode_profiles(profiles), True)
        if len(data) > MAX_FILE:
            raise ValueError("Los perfiles exceden el tamaño admitido.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=self.path.parent, delete=False) as file:
            temporary = Path(file.name)
            try:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            except BaseException:
                file.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
