"""Streaming low-pass PCM filtering before reducing the sample rate."""
from math import ceil


class DownsampleFilter:
    def __init__(self, source_rate, target_rate):
        import numpy as np

        self.np = np
        # Windowed sinc. Leave room for the transition band below target Nyquist.
        count = ceil(source_rate / 400) | 1
        cutoff = 0.425 * target_rate / source_rate
        offset = np.arange(count) - count // 2
        kernel = np.sinc(2 * cutoff * offset) * np.hamming(count)
        self.kernel = (kernel / kernel.sum()).astype(np.float32)
        self.step = source_rate // target_rate if source_rate % target_rate == 0 else 1
        self.tail = np.zeros(count - 1, dtype=np.float32)
        self.phase = 0

    def apply(self, pcm):
        np = self.np
        samples = np.frombuffer(pcm, dtype="<i2")
        combined = np.concatenate((self.tail, samples))
        if self.step == 1:
            filtered = np.convolve(combined, self.kernel, mode="valid")
        else:
            windows = np.lib.stride_tricks.sliding_window_view(combined, len(self.kernel))
            filtered = np.einsum("ij,j->i", windows[self.phase::self.step], self.kernel)
            self.phase = (self.phase - len(samples)) % self.step
        self.tail = combined[-len(self.tail):].copy()
        return np.clip(np.rint(filtered), -32768, 32767).astype("<i2").tobytes()

    def reset(self):
        self.phase = 0
        self.tail.fill(0)
