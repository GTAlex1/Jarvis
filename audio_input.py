"""Select a Windows input route, negotiate PCM and report its measured level."""
from array import array
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from math import log10
from queue import Empty, Full, Queue
import sys
from threading import Event
from time import monotonic

from pcm_resample import DownsampleFilter
from voice_diagnostics import LOG
from voice_recognition import RATE
from windows_audio import default_input, mapper_names, wasapi_endpoint_ids, wasapi_mix_formats

try:
    import audioop
except ImportError:
    audioop = None

from call_audio import playback_input

BACKENDS = ("Windows WASAPI", "MME", "Windows DirectSound", "ASIO")
AUTO_ORDER = ("MME", "Windows DirectSound", "Windows WASAPI", "ASIO")
DIGITAL_SILENCE = 1.2


class CaptureError(OSError):
    pass


class DefaultInputChanged(CaptureError):
    pass


@dataclass(frozen=True)
class Route:
    index: int
    name: str
    api: str
    rate: int
    channels: int
    legacy_key: str
    default: bool = False
    mapper: bool = False
    endpoint: str = ""
    mix: tuple | None = None


@dataclass(frozen=True)
class InputDevice:
    key: str
    label: str
    routes: tuple

    def matches(self, selection):
        return selection == self.key or any(route.legacy_key == selection for route in self.routes)


def same_name(first, second):
    a, b = first.name.strip().casefold(), second.name.strip().casefold()
    return a == b or (first.api == "MME" and len(a) >= 30 and b.startswith(a)) or (
        second.api == "MME" and len(b) >= 30 and a.startswith(b)
    )


@dataclass(frozen=True)
class Inputs:
    devices: tuple
    mappers: tuple

    def uses_default(self, selection):
        return not selection or any(route.legacy_key == selection for route in self.mappers)

    def key_for(self, selection):
        if self.uses_default(selection):
            return ""
        match = next((item for item in self.devices if item.matches(selection)), None)
        return match.key if match else selection

    def migrate(self, selection, interface):
        key = self.key_for(selection)
        if selection != key and not interface:
            sources = (*self.mappers, *(route for device in self.devices for route in device.routes))
            match = next((route for route in sources if route.legacy_key == selection), None)
            if match is not None:
                interface = match.api
        return key, interface

    def interfaces_for(self, selection):
        try:
            available = {route.api for route in self.routes_for(selection)}
            try:
                self.routes_for(selection, interface="ASIO")
            except CaptureError:
                pass
            else:
                available.add("ASIO")
            return available
        except CaptureError:
            return set()

    def routes_for(self, selection, endpoint=None, interface="", preferred=""):
        prefer_mapper = selection if self.uses_default(selection) else ""
        selection, interface = self.migrate(selection, interface)
        fallback = self.mappers
        default = next((item for item in self.devices
                        if endpoint and any(r.endpoint == endpoint for r in item.routes)), None)
        if default is None:
            default = next((item for api in BACKENDS for item in self.devices
                            if any(r.default and r.api == api for r in item.routes)), None)
        if not selection:
            primary = default
        else:
            primary = next((item for item in self.devices if item.matches(selection)), None)
            if primary is None:
                raise CaptureError("El micrófono seleccionado está desconectado.")
            if primary != default:
                fallback = ()
        routes = (primary.routes if primary else ()) + fallback
        if not interface:
            routes = tuple(route for route in routes if route.api != "ASIO")
        if interface:
            routes = tuple(route for route in routes if route.api == interface)
            if not routes:
                raise CaptureError(f"La entrada seleccionada no está disponible mediante {interface}.")
        return sorted(routes, key=lambda r: (
            r.legacy_key != prefer_mapper, preferred not in (r.legacy_key, r.api), AUTO_ORDER.index(r.api),
            r.mapper if selection else not r.mapper,
        ))


def group_routes(routes):
    physical = sorted((r for r in routes if not r.mapper),
                      key=lambda r: (r.api == "MME", BACKENDS.index(r.api), r.index))
    groups = []
    for route in physical:
        matches = [group for group in groups
                   if all(item.api != route.api for item in group) and
                   any(same_name(item, route) for item in group)]
        # An identical or truncated name can refer to multiple physical inputs.
        same_host = [item for item in physical if item.api == route.api and same_name(item, route)]
        if len(matches) == 1 and len(same_host) == 1:
            matches[0].append(route)
        else:
            groups.append([route])
    counts = Counter(group[0].name.casefold() for group in groups)
    seen = Counter()
    devices = []
    for group in groups:
        anchor = group[0]
        name = anchor.name
        seen[name.casefold()] += 1
        label = name if counts[name.casefold()] == 1 else f"{name} ({anchor.api} #{seen[name.casefold()]})"
        devices.append(InputDevice(anchor.endpoint or anchor.legacy_key, label, tuple(group)))
    return Inputs(tuple(sorted(devices, key=lambda item: item.label.casefold())),
                  tuple(r for r in routes if r.mapper))


@contextmanager
def portaudio():
    import sounddevice as sd

    yield sd


def input_devices(refresh=False):
    with portaudio() as sd:
        try:
            if refresh:
                if sd._initialized:
                    sd._terminate()
                sd._initialize()
            hosts = sd.query_hostapis()
            available = sd.query_devices()
        except sd.PortAudioError as error:
            raise CaptureError(f"PortAudio no pudo enumerar entradas: {error}") from error
        mappers = {}
        endpoints, mix = {}, {}
        if sys.platform == "win32" and any(item["max_input_channels"] for item in available):
            mappers = mapper_names()
            indices = [d["index"] for d in available if d["max_input_channels"] and
                       hosts[d["hostapi"]]["name"] == BACKENDS[0]]
            try:
                endpoints = wasapi_endpoint_ids(sd._libname, indices)
                mix = wasapi_mix_formats(sd._libname, indices)
            except OSError as error:
                LOG.warning("captura identidad WASAPI: %s", error)
    routes = []
    occurrences = Counter()
    for data in available:
        host = hosts[data["hostapi"]]
        api, name, index = host["name"], data["name"].strip(), data["index"]
        if api not in BACKENDS or not data["max_input_channels"] or playback_input(name):
            continue
        label = f"{name} ({api})"
        occurrences[label] += 1
        mapper = name.casefold() == mappers.get(api, "").casefold()
        # Older versions exposed the Windows mapper using a localized title.
        routes.append(Route(index, name, api, round(data["default_samplerate"]),
                            data["max_input_channels"], f"{label} #{occurrences[label]}",
                            index == host["default_input_device"], mapper, endpoints.get(index, ""), mix.get(index)))
    return group_routes(routes)


@dataclass(frozen=True)
class AudioFormat:
    rate: int
    channels: int
    convert: bool = False
    dtype: str = "int16"


def input_formats(route):
    formats = []
    if route.mix:
        rate, channels, dtype = route.mix
        if rate > 96000:
            formats.append(AudioFormat(48000, min(2, channels), True, dtype))
            formats.append(AudioFormat(RATE, 1, True))
        formats.append(AudioFormat(rate, channels, dtype=dtype))
        formats.append(AudioFormat(rate, channels, dtype="int16" if dtype == "float32" else "float32"))
        formats.append(AudioFormat(RATE, 1, True))
    rates = (RATE, 48000, 44100, 32000, 22050, 96000, 8000, route.rate)
    channels = dict.fromkeys((1, min(2, route.channels), route.channels))
    for rate in dict.fromkeys(rate for rate in rates if rate > 0):
        for count in channels:
            formats.append(AudioFormat(rate, count))
    if route.api == BACKENDS[0]:
        formats.append(AudioFormat(RATE, 1, True))
        for rate in dict.fromkeys(rate for rate in (RATE, 48000, 44100, route.rate) if rate > 0):
            for count in channels:
                formats.append(AudioFormat(rate, count, dtype="float32"))
    return dict.fromkeys(formats)


def reject_recognition(capture, rejected, whole_interface=False):
    index, fmt = capture.route.index, capture.format
    if capture.route.api == BACKENDS[0]:
        rejected.add((index, fmt))
        count = sum(isinstance(item, tuple) and item[0] == index for item in rejected)
        if count < 3:
            return
    rejected.add(index)
    if whole_interface:
        rejected.update(route.index for route in capture.available_routes if route.api == capture.route.api)


class PcmConverter:
    def __init__(self, audio_format):
        if audioop is None:
            raise ImportError("Instala audioop-lts desde requirements-voice.txt.")
        self.format = audio_format
        self.state = None
        self.filter = DownsampleFilter(audio_format.rate, RATE) if audio_format.rate > RATE else None

    def convert(self, raw):
        if not raw:
            return raw
        if self.format.dtype == "float32":
            floats = array("f")
            floats.frombytes(raw)
            raw = array("h", (round(max(-1.0, min(1.0, x)) * 32767) for x in floats)).tobytes()
        if self.format.channels > 1:
            samples = array("h")
            samples.frombytes(raw)
            channels = [samples[i::self.format.channels].tobytes() for i in range(self.format.channels)]
            # Preserve the active input when stereo channels have opposite polarity
            # or a microphone is wired to only one side.
            raw = max(channels, key=lambda channel: audioop.rms(channel, 2))
        return self.resample(raw)

    def resample(self, raw):
        if self.filter:
            raw = self.filter.apply(raw)
            if self.filter.step > 1:
                return raw
        if self.format.rate != RATE:
            raw, self.state = audioop.ratecv(raw, 2, 1, self.format.rate, RATE, self.state)
        return raw

    def reset(self):
        self.state = None
        if self.filter:
            self.filter.reset()


class Microphone:
    def __init__(self, sd, route, audio_format, native_settings, current_default, expected_default):
        self.sd = sd
        self.route = route
        self.available_routes = ()
        self.automatic = False
        self.notice = ""
        self.format = audio_format
        self.current_default = current_default
        self.expected_default = expected_default
        self.default_check_at = 0.0
        self.audio = Queue(maxsize=160)
        self.capturing = Event()
        self.capturing.set()
        self.ended = Event()
        self.overflow = Event()
        self.converter = PcmConverter(audio_format)
        self.low_pass_state = None
        self.driver_overflow = Event()
        self.last_warning = 0.0
        self.level = 0
        self.peak = 0
        self.prefetch = None
        self.verified = False
        self.stream = sd.RawInputStream(
            **native_settings, blocksize=0 if route.api == BACKENDS[0] else max(1, audio_format.rate // 20),
            latency="high",
            callback=self.receive, finished_callback=self.ended.set,
        )

    @property
    def label(self):
        return (f"{self.route.name} · {self.route.api} · {self.format.rate} Hz · "
                f"{self.format.channels} canal(es) · {self.format.dtype}")

    def receive(self, indata, _frames, _time, status):
        if self.capturing.is_set():
            if status and status.input_overflow:
                self.driver_overflow.set()
            try:
                self.audio.put_nowait(bytes(indata))
            except Full:
                self.overflow.set()

    def __enter__(self):
        try:
            self.stream.start()
        except self.sd.PortAudioError:
            self.stream.close()
            raise
        self.last_input = monotonic()
        return self

    def __exit__(self, *_error):
        try:
            self.stream.close()
        except self.sd.PortAudioError as error:
            LOG.warning("captura cierre %s: %s", self.label, error)

    def read(self, timeout=0.2):
        if self.prefetch is not None:
            pcm, self.prefetch = self.prefetch, None
            return pcm
        if self.current_default and monotonic() >= self.default_check_at:
            self.default_check_at = monotonic() + 1
            if self.current_default() != self.expected_default:
                raise DefaultInputChanged("Cambió el micrófono predeterminado de Windows.")
        try:
            active = self.stream.active
        except self.sd.PortAudioError as error:
            raise CaptureError(f"{self.label}: {error}") from error
        if self.overflow.is_set():
            raise CaptureError(f"{self.label}: se saturó la cola de captura.")
        if self.ended.is_set() or not active:
            raise CaptureError(f"{self.label}: Windows interrumpió la captura.")
        try:
            raw = self.audio.get(timeout=timeout)
        except Empty:
            if monotonic() - self.last_input > 1.5:
                raise CaptureError(f"{self.label}: el controlador no entrega audio.")
            return None
        self.last_input = monotonic()
        pcm = self.converter.convert(raw)
        if pcm:
            # Software-only high-pass around 80 Hz to attenuate DC and low rumble.
            low, self.low_pass_state = audioop.ratecv(pcm, 2, 1, RATE, RATE, self.low_pass_state, 1, 30)
            pcm = audioop.add(pcm, audioop.mul(low, 2, -1), 2)
        if self.driver_overflow.is_set():
            self.driver_overflow.clear()
            now = monotonic()
            if now - self.last_warning >= 10:
                LOG.warning("captura: el controlador descartó bloques de %s", self.label)
                self.last_warning = now
        amplitude = audioop.rms(pcm, 2)
        self.peak = max(self.peak, amplitude)
        self.level = min(100, max(0, round((20 * log10(max(amplitude, 1) / 32768) + 60) / 0.6)))
        return pcm

    def pause(self):
        self.capturing.clear()
        self.level = 0

    def resume(self):
        while True:
            try:
                self.audio.get_nowait()
            except Empty:
                break
        self.converter.reset()
        self.low_pass_state = None
        self.last_input = monotonic()
        self.capturing.set()


def probe(capture, changed):
    deadline = monotonic() + DIGITAL_SILENCE
    received = False
    while not changed.is_set() and monotonic() < deadline:
        pcm = capture.read()
        received |= pcm is not None
        if capture.peak:
            capture.prefetch = pcm
            return True
    if not received and not changed.is_set():
        raise CaptureError(f"{capture.label}: no recibió bloques de audio al iniciar.")
    return False


@contextmanager
def capture_input(catalog, selection, changed, rejected=(), interface="", preferred="", recover_interface=False):
    with ExitStack() as session, portaudio() as sd:
        current, endpoint = None, None
        if sys.platform == "win32":
            try:
                read_default = session.enter_context(default_input())
                endpoint = read_default()
                if catalog.uses_default(selection):
                    current = read_default
            except OSError as error:
                LOG.warning("captura predeterminado: %s", error)
        note = ""
        try:
            routes = catalog.routes_for(selection, endpoint, interface, preferred)
        except CaptureError:
            if not (recover_interface and interface):
                raise
            routes = catalog.routes_for(selection, endpoint, preferred=preferred)
            if not routes:
                raise
            note = f"{interface} no está disponible para esta entrada. Se usa la selección automática."
            LOG.warning("captura: %s", note)
            interface = ""
        silent = None
        failures = []
        for route in routes:
            if route.index in rejected:
                continue
            silent_formats = 0
            for fmt in input_formats(route):
                if (route.index, fmt) in rejected:
                    continue
                if changed.is_set():
                    yield None
                    return
                options = dict(device=route.index, samplerate=fmt.rate, channels=fmt.channels,
                               dtype=fmt.dtype, extra_settings=sd.WasapiSettings(exclusive=False, auto_convert=fmt.convert)
                               if route.api == BACKENDS[0] else None)
                with ExitStack() as attempt:
                    try:
                        sd.check_input_settings(**options)
                        capture = attempt.enter_context(Microphone(sd, route, fmt, options, current, endpoint))
                        capture.verified = probe(capture, changed)
                    except DefaultInputChanged:
                        raise
                    except (CaptureError, sd.PortAudioError) as error:
                        failure = f"{route.api} {route.name} {fmt.rate} Hz/{fmt.channels}/{fmt.dtype}: {error}"
                        LOG.info("captura formato rechazado: %s", failure)
                        failures.append(failure)
                        continue
                    if changed.is_set():
                        yield None
                        return
                    if capture.verified:
                        capture.available_routes = routes
                        capture.automatic = not interface
                        capture.notice = note
                        LOG.info("captura activa %s", capture.label)
                        yield capture
                        return
                    LOG.warning("captura silencio digital %s", capture.label)
                    if silent is None:
                        silent = (route, fmt, options)
                    silent_formats += 1
                    if route.api != BACKENDS[0] or not route.mix or silent_formats >= 3:
                        break
        if silent and not changed.is_set():
            route, fmt, options = silent
            try:
                capture = session.enter_context(Microphone(sd, route, fmt, options, current, endpoint))
            except sd.PortAudioError as error:
                raise CaptureError(f"No se pudo reabrir la entrada silenciosa: {error}") from error
            capture.available_routes = routes
            capture.automatic = not interface
            capture.notice = note
            yield capture
            return
        if changed.is_set():
            yield None
            return
        message = failures[-1] if failures else "No hay otra ruta de entrada disponible."
        raise CaptureError(message)
