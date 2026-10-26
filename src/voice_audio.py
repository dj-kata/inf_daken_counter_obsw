"""Blocking WAV playback on a selected Qt audio output, for voice workers."""

from io import BytesIO
import wave

from PySide6.QtCore import QBuffer, QEventLoop, QIODevice, QThread, QTimer
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QtAudio


def audio_output_devices():
    return [(bytes(device.id()).hex(), device.description())
            for device in QMediaDevices.audioOutputs()]


def resolve_audio_device(device_id):
    if device_id:
        for device in QMediaDevices.audioOutputs():
            if bytes(device.id()).hex() == device_id:
                return device
        raise RuntimeError('選択した音声出力デバイスが見つかりません')
    device = QMediaDevices.defaultAudioOutput()
    if device.isNull():
        raise RuntimeError('音声出力デバイスがありません')
    return device


def wav_pcm(wav):
    with wave.open(BytesIO(wav), 'rb') as source:
        formats = {
            1: QAudioFormat.SampleFormat.UInt8,
            2: QAudioFormat.SampleFormat.Int16,
            4: QAudioFormat.SampleFormat.Int32,
        }
        sample_format = formats.get(source.getsampwidth())
        if sample_format is None:
            raise ValueError('対応していないWAVサンプル形式です')
        audio_format = QAudioFormat()
        audio_format.setSampleRate(source.getframerate())
        audio_format.setChannelCount(source.getnchannels())
        audio_format.setSampleFormat(sample_format)
        return source.readframes(source.getnframes()), audio_format


class _PlaybackThread(QThread):
    """Own the sink and its event loop on a Qt thread, never on the GUI thread."""
    def __init__(self, wav, device_id):
        super().__init__()
        self.wav = wav
        self.device_id = device_id
        self.failure = None

    def run(self):
        sink = None
        timeout = None
        state_timer = None
        try:
            pcm, audio_format = wav_pcm(self.wav)
            if not pcm:
                return
            device = resolve_audio_device(self.device_id)
            if not device.isFormatSupported(audio_format):
                raise RuntimeError('音声出力デバイスがWAVの形式に対応していません')
            loop = QEventLoop()
            buffer = QBuffer()
            buffer.setData(pcm)
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            sink = QAudioSink(device, audio_format)

            def check_state():
                if sink.state() in (QtAudio.State.IdleState, QtAudio.State.StoppedState):
                    loop.quit()

            # Some Windows/PySide builds cannot marshal the QAudio::State
            # signal argument. Read the state on the sink's own thread instead.
            state_timer = QTimer()
            state_timer.setInterval(20)
            state_timer.timeout.connect(check_state)
            timeout = QTimer()
            timeout.setSingleShot(True)
            timeout.timeout.connect(loop.quit)
            duration_ms = audio_format.durationForBytes(len(pcm)) // 1000
            timeout.start(int(duration_ms + 5000))
            sink.start(buffer)
            if sink.state() in (QtAudio.State.ActiveState, QtAudio.State.SuspendedState):
                state_timer.start()
                loop.exec()
            if not timeout.isActive():
                raise RuntimeError('音声再生がタイムアウトしました')
            if sink.error() != QtAudio.Error.NoError:
                raise RuntimeError(f'音声再生に失敗しました: {sink.error()}')
        except Exception as error:
            # Do not retain this thread's Qt objects through an exception frame.
            self.failure = error.with_traceback(None)
        finally:
            if state_timer is not None:
                state_timer.stop()
            if timeout is not None:
                timeout.stop()
            if sink is not None:
                sink.stop()


def play_wav(wav, device_id=''):
    worker = _PlaybackThread(wav, device_id)
    worker.start()
    worker.wait()
    if worker.failure is not None:
        raise worker.failure
