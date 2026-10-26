"""Run: QT_QPA_PLATFORM=offscreen .codex-venv/bin/python -B -m unittest misc.test_voice_audio"""

from io import BytesIO
import unittest
from unittest.mock import Mock, patch
import wave

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QAudioFormat, QtAudio

from src import voice_audio as audio


def wav_data(width=2):
    output = BytesIO()
    with wave.open(output, 'wb') as target:
        target.setnchannels(1)
        target.setsampwidth(width)
        target.setframerate(24000)
        target.writeframes(b'\0' * width * 240)
    return output.getvalue()


class FakeSink(QObject):
    @property
    def stateChanged(self):
        # Playback must work without connecting the enum signal which fails
        # argument conversion on the reported Windows/PySide configuration.
        raise AssertionError('stateChanged must not be connected')

    def __init__(self, error):
        super().__init__()
        self._state = QtAudio.State.StoppedState
        self._error = error
        self.stopped = False
        self.played = b''

    def start(self, buffer):
        self.played = bytes(buffer.readAll())
        self._state = QtAudio.State.ActiveState
        QTimer.singleShot(1, self.finish)

    def finish(self):
        self._state = (QtAudio.State.IdleState if self._error == QtAudio.Error.NoError
                       else QtAudio.State.StoppedState)

    def state(self):
        return self._state

    def error(self):
        return self._error

    def stop(self):
        self.stopped = True


class VoiceAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_device_ids_and_descriptions_and_default_selection(self):
        device = Mock()
        device.id.return_value = b'headphones'
        device.description.return_value = 'Headphones'
        device.isNull.return_value = False
        with patch.object(audio.QMediaDevices, 'audioOutputs', return_value=[device]), \
                patch.object(audio.QMediaDevices, 'defaultAudioOutput', return_value=device):
            identifier = b'headphones'.hex()
            self.assertEqual(audio.audio_output_devices(), [(identifier, 'Headphones')])
            self.assertIs(audio.resolve_audio_device(identifier), device)
            self.assertIs(audio.resolve_audio_device(''), device)
            with self.assertRaisesRegex(RuntimeError, '見つかりません'):
                audio.resolve_audio_device('missing')

    def test_no_default_output_reports_failure(self):
        device = Mock()
        device.isNull.return_value = True
        with patch.object(audio.QMediaDevices, 'defaultAudioOutput', return_value=device):
            with self.assertRaisesRegex(RuntimeError, 'ありません'):
                audio.resolve_audio_device('')

    def test_wav_header_is_removed_and_pcm_format_is_preserved(self):
        pcm, fmt = audio.wav_pcm(wav_data())
        self.assertEqual(pcm, b'\0' * 480)
        self.assertEqual(fmt.sampleRate(), 24000)
        self.assertEqual(fmt.channelCount(), 1)
        self.assertEqual(fmt.sampleFormat(), QAudioFormat.SampleFormat.Int16)
        with self.assertRaises(ValueError):
            audio.wav_pcm(wav_data(width=3))

    def test_completion_without_state_signal_still_stops_and_returns(self):
        self.check_playback(QtAudio.Error.NoError)

    def test_sink_failure_is_propagated_to_voice_worker(self):
        self.check_playback(QtAudio.Error.IOError)

    def check_playback(self, error):
        device = Mock()
        device.isFormatSupported.return_value = True
        sinks = []

        def create_sink(selected, fmt):
            self.assertIs(selected, device)
            sink = FakeSink(error)
            sinks.append(sink)
            return sink

        with patch.object(audio, 'resolve_audio_device', return_value=device) as resolve, \
                patch.object(audio, 'QAudioSink', side_effect=create_sink):
            if error == QtAudio.Error.NoError:
                audio.play_wav(wav_data(), 'chosen-id')
            else:
                with self.assertRaisesRegex(RuntimeError, '音声再生に失敗'):
                    audio.play_wav(wav_data(), 'chosen-id')
            resolve.assert_called_once_with('chosen-id')
        self.assertEqual(sinks[0].played, b'\0' * 480)
        self.assertTrue(sinks[0].stopped)

    def test_unsupported_format_does_not_start_sink(self):
        device = Mock()
        device.isFormatSupported.return_value = False
        with patch.object(audio, 'resolve_audio_device', return_value=device), \
                patch.object(audio, 'QAudioSink') as sink:
            with self.assertRaisesRegex(RuntimeError, '形式に対応していません'):
                audio.play_wav(wav_data(), 'chosen-id')
            sink.assert_not_called()


if __name__ == '__main__':
    unittest.main()
