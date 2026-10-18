"""PlotLoop Rec-Espresso: End-to-end lightning audio extraction & archiving pipeline.
"""

__version__ = "0.1.0"
__author__ = "granken"

from .asr import ASRAdapter, VolcengineASR, WhisperASR, MockASR
from .hotwords import HotwordsReplacer
from .archiver import AudioArchiver, ArchiveResult
from .diarization import CognitiveDiarizer
from .summarizer import StrategicSummarizer
from .pipeline import EspressoPipeline

__all__ = [
    "ASRAdapter",
    "VolcengineASR",
    "WhisperASR",
    "MockASR",
    "HotwordsReplacer",
    "AudioArchiver",
    "ArchiveResult",
    "CognitiveDiarizer",
    "StrategicSummarizer",
    "EspressoPipeline",
]
