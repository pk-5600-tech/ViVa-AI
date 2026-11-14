import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import threading
import time
import os
import re
import numpy as np
import tempfile


class SpeechAnalyzer:


    def __init__(self):

        print("Loading Whisper model...")

        self.model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8"
        )

        print("Whisper ready")

        self.recording = False
        self.audio = []
        self.stream = None
        self.recording_error = None

        self.sample_rate = 16000

        self.filename = None



    def start_recording(self):
        self.audio = []
        self.recording_error = None
        self.recording = True
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self.record,
            )
            self.stream.start()
        except Exception as exc:
            self.recording = False
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception:
                    pass
            self.stream = None
            raise RuntimeError("Microphone could not be opened. Check microphone permissions and availability.") from exc



    def record(self, indata, frames, time_info, status):

        if status:
            self.recording_error = str(status)
        if self.recording:
            self.audio.append(indata.copy())




    def stop_recording(self):
        self.recording = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.recording_error:
            raise RuntimeError(f"Microphone recording reported an error: {self.recording_error}")
        if not self.audio:
            raise RuntimeError("No audio was recorded. Check microphone permissions and try again.")

        audio_data = np.concatenate(self.audio, axis=0).astype(np.float32, copy=False)
        with tempfile.NamedTemporaryFile(prefix="vivamate-", suffix=".wav", delete=False) as temp_audio:
            self.filename = temp_audio.name
        write(self.filename, self.sample_rate, audio_data)
        return self.filename




    def analyze(self, filename):


        # model = WhisperModel(
        #     "base",
        #     compute_type="int8"
        # )


        segments, info = self.model.transcribe(
            filename
        )


        transcript=""


        for segment in segments:

            transcript += segment.text+" "



        transcript = transcript.lower()



        fillers=[

            "um",
            "uh",
            "like",
            "basically",
            "actually",
            "you know",
            "so"

        ]


        counts={}


        for word in fillers:

            counts[word] = len(
                re.findall(
                    re.escape(word),
                    transcript
                )
            )

        total_fillers = sum(
            counts.values()
        )


        duration = info.duration



        # simple fluency score

        words=len(
            transcript.split()
        )


        if duration>0:

            words_per_minute = (
                words/duration
            )*60

        else:

            words_per_minute=0



        if words > 0:

            filler_ratio = (
                total_fillers / words
            )

        else:

            filler_ratio = 0


        if 90 <= words_per_minute <= 160:

            fluency = 1

        else:

            fluency = 0.8


        fluency = max(
            0.5,
            fluency - (filler_ratio * 2)
        )

        print("\nTranscript:")
        print(transcript)
        print("\nFillers:")
        print(counts)


        return {


            "duration":
            round(duration,2),


            "speech_fluency":
            fluency,


            "fillers":
            counts,


            "transcript":
            transcript,

            "words_per_minute": round(
                words_per_minute,
                1
            )
        }
