"""asr.py · Automatic Speech Recognition (ASR) Adapters.
"""
from __future__ import annotations

import abc
import os
import re
import shutil
import subprocess
import time
from typing import Dict, Any, Optional, List


class ASRAdapter(abc.ABC):
    """Abstract base class for speech-to-text engines."""

    @abc.abstractmethod
    def transcribe(self, audio_path: str, output_dir: str, basename: Optional[str] = None) -> str:
        """Transcribe an audio file and return the path to the resulting Markdown transcript."""
        pass


class VolcengineASR(ASRAdapter):
    """Volcengine SeedASR AUC Adapter.

    Uses `recording-transcribe` CLI or direct API configuration to generate
    high-fidelity speech-to-text with millisecond acoustic diarization.
    """

    def __init__(
        self,
        binary_path: Optional[str] = None,
        speaker_info: bool = True,
        extra_args: Optional[List[str]] = None
    ):
        self.binary_path = binary_path or shutil.which("recording-transcribe") or "recording-transcribe"
        self.speaker_info = speaker_info
        self.extra_args = extra_args or []

    def transcribe(self, audio_path: str, output_dir: str, basename: Optional[str] = None) -> str:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        os.makedirs(output_dir, exist_ok=True)
        base = basename or os.path.splitext(os.path.basename(audio_path))[0]
        safe_base = re.sub(r"[\s\(\)]+", "_", base).strip("_")

        cmd = [
            self.binary_path,
            "--output-dir", output_dir,
            "--basename", safe_base,
        ]
        if self.speaker_info:
            cmd.append("--speaker-info")
        cmd.extend(self.extra_args)
        cmd.append(audio_path)

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Volcengine SeedASR failed: {proc.stderr or proc.stdout}")

        expected_md = os.path.join(output_dir, f"{safe_base}_转写.md")
        if not os.path.exists(expected_md):
            # Fallback check for English naming convention
            fallback_md = os.path.join(output_dir, f"{safe_base}_transcript.md")
            if os.path.exists(fallback_md):
                return fallback_md
            # Return expected even if file naming differs slightly
            return expected_md
        return expected_md


class WhisperASR(ASRAdapter):
    """OpenAI Whisper / faster-whisper CLI Adapter."""

    def __init__(
        self,
        binary_path: Optional[str] = None,
        model: str = "turbo",
        language: Optional[str] = "zh",
        extra_args: Optional[List[str]] = None
    ):
        self.binary_path = binary_path or shutil.which("whisper") or "whisper"
        self.model = model
        self.language = language
        self.extra_args = extra_args or []

    def transcribe(self, audio_path: str, output_dir: str, basename: Optional[str] = None) -> str:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        os.makedirs(output_dir, exist_ok=True)
        base = basename or os.path.splitext(os.path.basename(audio_path))[0]
        safe_base = re.sub(r"[\s\(\)]+", "_", base).strip("_")

        cmd = [
            self.binary_path,
            audio_path,
            "--model", self.model,
            "--output_dir", output_dir,
            "--output_format", "txt",
        ]
        if self.language:
            cmd.extend(["--language", self.language])
        cmd.extend(self.extra_args)

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Whisper transcription failed: {proc.stderr or proc.stdout}")

        raw_txt = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(audio_path))[0]}.txt")
        target_md = os.path.join(output_dir, f"{safe_base}_transcript.md")

        if os.path.exists(raw_txt):
            # Wrap plain text into markdown transcript
            with open(raw_txt, "r", encoding="utf-8") as f_in:
                content = f_in.read()
            with open(target_md, "w", encoding="utf-8") as f_out:
                f_out.write(f"# Transcript: {safe_base}\n\n")
                f_out.write(content)
            return target_md

        return target_md


class MockASR(ASRAdapter):
    """Mock ASR Engine for offline testing, demos, and CI verification."""

    def __init__(self, sample_text: Optional[str] = None):
        self.sample_text = sample_text or (
            "[00:00:01 - 00:00:15] Speaker 1: Welcome everyone. Let us review the Q3 architecture roadmap.\n"
            "[00:00:16 - 00:00:45] Speaker 2: We have evaluated the on-premise AI appliance benchmarks.\n"
            "[00:00:46 - 00:01:20] Speaker 1: The key takeaway is privacy and turnkey deployment for enterprise.\n"
        )

    def transcribe(self, audio_path: str, output_dir: str, basename: Optional[str] = None) -> str:
        os.makedirs(output_dir, exist_ok=True)
        base = basename or os.path.splitext(os.path.basename(audio_path))[0]
        safe_base = re.sub(r"[\s\(\)]+", "_", base).strip("_")
        out_file = os.path.join(output_dir, f"{safe_base}_transcript.md")

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"# Mock Transcript: {safe_base}\n\n")
            f.write(self.sample_text)

        return out_file
