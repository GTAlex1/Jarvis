from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

import numpy as np

from biometric_audio import Reason, Reading, contiguous, extract, quality, verify
from speakers import Profile
from test_voice import PROFILE, SAMPLE
from voice_probe import fixture
from voice_recognition import CHUNK_FRAMES, RATE, SAMPLE_BYTES, SpanishRecognizer, local_speaker_model, spanish_model

FIXTURES = Path(__file__).with_name("tests") / "voice"


class AudioQualityTest(TestCase):
    def test_silence_noise_clipping_and_internal_error_are_distinct(self):
        self.assertEqual(quality(bytes(RATE * SAMPLE_BYTES)).reason, Reason.SILENCE)
        noise = np.random.default_rng(3).integers(-2000, 2000, RATE, dtype="<i2").tobytes()
        self.assertEqual(quality(noise).reason, Reason.NOISE)
        clip = np.full(RATE, 32767, dtype="<i2").tobytes()
        self.assertEqual(quality(clip).reason, Reason.CLIPPING)
        self.assertEqual(verify(Mock(side_effect=ValueError), b"", b"", (PROFILE,), 0.72)[0], Reason.ERROR)
        self.assertEqual(verify(Mock(), b"", b"", (), 0.72)[0], Reason.MISSING)

    def test_a_sufficient_command_never_borrows_the_wake_sample(self):
        lookup = Mock(return_value=Reading(None, sample=SAMPLE))
        self.assertEqual(verify(lookup, b"order", b"wake", (PROFILE,), 0.72, expected="another"),
                         (Reason.UNAUTHORIZED, None))
        lookup.assert_called_once_with(b"order")


class SyntheticBiometricTest(TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.model, cls.speaker = spanish_model(), local_speaker_model()
        except (ImportError, OSError) as error:
            from unittest import SkipTest

            raise SkipTest(str(error)) from error

    def extract(self, audio):
        return extract(self.model, self.speaker, audio)

    def test_same_synthetic_speaker_matches_independent_phrase(self):
        first = self.extract(fixture(FIXTURES, "open-spotify")).sample
        same = fixture(FIXTURES, "stop")
        other = fixture(FIXTURES, "wake-en")
        profile = Profile("probe", "Sintético", (first.vector,) * 3)
        self.assertEqual(verify(self.extract, same, b"", (profile,), 0.72), (Reason.ACCEPTED, "probe"))
        self.assertEqual(verify(self.extract, other, b"", (profile,), 0.72), (Reason.UNAUTHORIZED, None))

    def test_short_synthetic_command_only_borrows_contiguous_wake_audio(self):
        utterance = fixture(FIXTURES, "stop")
        wake, short = utterance[:28400], utterance[28400:]
        profile_sample = self.extract(fixture(FIXTURES, "open-spotify")).sample
        profile = Profile("probe", "Sintético", (profile_sample.vector,) * 3)
        self.assertEqual(self.extract(short).reason, Reason.SHORT)
        self.assertTrue(contiguous(wake, short))
        self.assertEqual(verify(self.extract, short, wake, (profile,), 0.72)[0], Reason.ACCEPTED)
        separated = bytes(RATE * SAMPLE_BYTES // 2) + short
        self.assertFalse(contiguous(wake, separated))
        self.assertEqual(verify(self.extract, separated, wake, (profile,), 0.72)[0], Reason.SHORT)

    def test_words_can_be_decoded_without_the_minimum_biometric_frames(self):
        audio = bytes(RATE) + fixture(FIXTURES, "stop")[28400:] + bytes(RATE * SAMPLE_BYTES)
        decoder = SpanishRecognizer(self.model, speaker_model=self.speaker)
        step = CHUNK_FRAMES * SAMPLE_BYTES
        results = [decoder.feed(audio[i:i + step]) for i in range(0, len(audio), step)]
        results.append(decoder.finish())
        answers = [item for item in results if item]
        self.assertTrue(answers)
        self.assertTrue(all(item.speaker is None for item in answers))
