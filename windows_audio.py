"""Small Windows adapters for endpoint identity and the current default input."""
from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from uuid import UUID
from struct import unpack_from

CLSID_ENUMERATOR = UUID("bcde0395-e52f-467c-8e3d-c4579291692e")
IID_ENUMERATOR = UUID("a95664d2-9614-4f35-a746-de8db63617e6")
NO_ENDPOINT = 0x80070490
APARTMENT_ALREADY_SET = 0x80010106


def method(obj, index, result, *params):
    table = c.cast(obj, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(result, c.c_void_p, *params)(table[index])


def endpoint_id(device):
    identifier = c.c_void_p()
    status = method(device, 5, c.c_long, c.POINTER(c.c_void_p))(device, c.byref(identifier))
    if status < 0:
        raise OSError(f"IMMDevice.GetId: 0x{status & 0xffffffff:08x}")
    try:
        return c.wstring_at(identifier).casefold()
    finally:
        c.windll.ole32.CoTaskMemFree(identifier)


@contextmanager
def default_input():
    ole = c.windll.ole32
    ole.CoInitializeEx.argtypes = [c.c_void_p, w.DWORD]
    ole.CoInitializeEx.restype = c.c_long
    ole.CoCreateInstance.argtypes = [c.c_void_p, c.c_void_p, w.DWORD, c.c_void_p, c.POINTER(c.c_void_p)]
    ole.CoCreateInstance.restype = c.c_long
    ole.CoTaskMemFree.argtypes = [c.c_void_p]
    status = ole.CoInitializeEx(None, 2)
    owns_apartment = status >= 0
    if not owns_apartment and status & 0xffffffff != APARTMENT_ALREADY_SET:
        raise OSError(f"CoInitializeEx: 0x{status & 0xffffffff:08x}")
    enumerator = c.c_void_p()
    try:
        clsid = (c.c_ubyte * 16).from_buffer_copy(CLSID_ENUMERATOR.bytes_le)
        iid = (c.c_ubyte * 16).from_buffer_copy(IID_ENUMERATOR.bytes_le)
        status = ole.CoCreateInstance(clsid, None, 1, iid, c.byref(enumerator))
        if status < 0:
            raise OSError(f"IMMDeviceEnumerator: 0x{status & 0xffffffff:08x}")
        get_endpoint = method(enumerator, 4, c.c_long, c.c_int, c.c_int, c.POINTER(c.c_void_p))

        def current():
            device = c.c_void_p()
            status = get_endpoint(enumerator, 1, 0, c.byref(device))  # eCapture, eConsole
            if status & 0xffffffff == NO_ENDPOINT:
                return None
            if status < 0:
                raise OSError(f"GetDefaultAudioEndpoint: 0x{status & 0xffffffff:08x}")
            try:
                return endpoint_id(device)
            finally:
                method(device, 2, w.ULONG)(device)

        yield current
    finally:
        if enumerator:
            method(enumerator, 2, w.ULONG)(enumerator)
        if owns_apartment:
            ole.CoUninitialize()


def wasapi_endpoint_ids(library, indices):
    if not indices:
        return {}
    # Use the same PortAudio DLL already initialized by sounddevice.
    try:
        get_device = c.CDLL(library).PaWasapi_GetIMMDevice
    except (AttributeError, OSError):
        return {}
    get_device.argtypes = [c.c_int, c.POINTER(c.c_void_p)]
    get_device.restype = c.c_int
    endpoints = {}
    for index in indices:
        device = c.c_void_p()
        if get_device(index, c.byref(device)) == 0 and device:
            # PortAudio owns this IMMDevice pointer.
            endpoints[index] = endpoint_id(device)
    return endpoints


def decode_mix_format(data):
    if len(data) < 16:
        return None
    tag, channels, rate, _, _, bits = unpack_from("<HHIIHH", data)
    if tag == 0xfffe and len(data) >= 40:
        tag = unpack_from("<I", data, 24)[0]
    if not 8000 <= rate <= 384000 or not 1 <= channels <= 32:
        return None
    if tag == 3 and bits == 32:
        return rate, channels, "float32"
    if tag == 1 and bits in (16, 24, 32):
        return rate, channels, "int16" if bits == 16 else "float32"
    return None


def wasapi_mix_formats(library, indices):
    if not indices:
        return {}
    try:
        library = c.CDLL(library)
        query = getattr(library, "PaWasapi_GetDeviceMixFormat", None) or library.PaWasapi_GetDeviceDefaultFormat
    except (AttributeError, OSError):
        return {}
    query.argtypes = [c.c_void_p, c.c_uint, c.c_int]
    query.restype = c.c_int
    formats = {}
    for index in indices:
        buf = c.create_string_buffer(64)
        size = query(buf, c.sizeof(buf), index)
        if size > 0 and (fmt := decode_mix_format(buf.raw[:size])):
            formats[index] = fmt
    return formats


def mapper_names():
    class WaveCaps(c.Structure):
        _fields_ = [
            ("manufacturer", w.WORD), ("product", w.WORD), ("version", w.DWORD),
            ("name", w.WCHAR * 32), ("formats", w.DWORD), ("channels", w.WORD), ("reserved", w.WORD),
        ]

    winmm = c.windll.winmm
    caps = WaveCaps()
    get_caps = winmm.waveInGetDevCapsW
    get_caps.argtypes = [c.c_size_t, c.POINTER(WaveCaps), w.UINT]
    get_caps.restype = w.UINT
    mme = caps.name if get_caps(0xffffffff, c.byref(caps), c.sizeof(caps)) == 0 else ""
    names = []

    @c.WINFUNCTYPE(w.BOOL, c.c_void_p, w.LPCWSTR, w.LPCWSTR, c.c_void_p)
    def collect(guid, description, _module, _data):
        if not guid and description:
            names.append(description)
        return True

    try:
        enumerate_devices = c.windll.dsound.DirectSoundCaptureEnumerateW
        enumerate_devices.argtypes = [type(collect), c.c_void_p]
        enumerate_devices.restype = c.c_long
        enumerate_devices(collect, None)
    except OSError:
        pass
    return {"MME": mme + " - Input" if mme else "Microsoft Sound Mapper - Input",
            "Windows DirectSound": names[0] if names else "Primary Sound Capture Driver"}
