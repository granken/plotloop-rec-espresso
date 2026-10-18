"""pipeline.py · Main PlotLoop Rec-Espresso Pipeline Orchestrator.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Any

from .asr import ASRAdapter, VolcengineASR, WhisperASR, MockASR
from .hotwords import HotwordsReplacer
from .diarization import CognitiveDiarizer
from .summarizer import StrategicSummarizer
from .archiver import AudioArchiver, ArchiveResult


SUPPORTED_EXTS = (".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".m4b")


@dataclasses.dataclass
class PipelineResult:
    audio_file: str
    transcript_path: Optional[str] = None
    summary_path: Optional[str] = None
    archive_result: Optional[ArchiveResult] = None
    elapsed_seconds: float = 0.0
    success: bool = True
    error: Optional[str] = None


class EspressoPipeline:
    """Orchestrates end-to-end lightning transcription, diarization, synthesis, and archiving."""

    def __init__(
        self,
        asr_adapter: Optional[ASRAdapter] = None,
        hotwords_replacer: Optional[HotwordsReplacer] = None,
        diarizer: Optional[CognitiveDiarizer] = None,
        summarizer: Optional[StrategicSummarizer] = None,
        archiver: Optional[AudioArchiver] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or {}
        self.asr = asr_adapter or self._init_default_asr()
        self.hotwords = hotwords_replacer
        self.diarizer = diarizer or CognitiveDiarizer()
        self.summarizer = summarizer or StrategicSummarizer()
        self.archiver = archiver

    def _init_default_asr(self) -> ASRAdapter:
        asr_cfg = self.config.get("asr", {})
        provider = asr_cfg.get("provider", "volcengine").lower()

        if provider == "volcengine":
            sub_cfg = asr_cfg.get("volcengine", {})
            return VolcengineASR(
                binary_path=sub_cfg.get("binary_path"),
                speaker_info=sub_cfg.get("speaker_diarization", True)
            )
        elif provider == "whisper":
            sub_cfg = asr_cfg.get("whisper", {})
            return WhisperASR(
                binary_path=sub_cfg.get("binary_path"),
                model=sub_cfg.get("model", "turbo"),
                language=sub_cfg.get("language", "zh")
            )
        elif provider == "mock":
            return MockASR()
        return VolcengineASR()

    @classmethod
    def from_config_file(cls, config_path: str) -> "EspressoPipeline":
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # Hotwords
        hw_cfg = cfg.get("hotwords", {})
        hotwords = None
        if hw_cfg.get("enabled", True):
            gfile = hw_cfg.get("glossary_file")
            if gfile and os.path.exists(gfile):
                hotwords = HotwordsReplacer.from_file(gfile)
            else:
                hotwords = HotwordsReplacer(hw_cfg.get("custom_replacements", {}))

        # Archiver
        arc_cfg = cfg.get("archiver", {})
        archiver = None
        if arc_cfg.get("enabled", False):
            smb_info = arc_cfg.get("smb", {})
            archiver = AudioArchiver(
                target_dir=arc_cfg.get("local_backup_dir", "~/Backups/audio-archive"),
                smb_host=smb_info.get("host"),
                smb_share=smb_info.get("share"),
                verify_sha256=arc_cfg.get("verify_sha256", True),
                prune_original=arc_cfg.get("prune_original", False),
                ledger_path=arc_cfg.get("ledger", {}).get("path")
            )

        return cls(hotwords_replacer=hotwords, archiver=archiver, config=cfg)

    @staticmethod
    def collect_audio_files(inputs: List[str]) -> List[str]:
        """Collect and deduplicate supported audio files from paths or directories."""
        collected: List[str] = []
        for item in inputs:
            p = os.path.abspath(os.path.expanduser(item))
            if os.path.isdir(p):
                for root, _, fnames in os.walk(p):
                    for f in sorted(fnames):
                        if f.lower().endswith(SUPPORTED_EXTS):
                            collected.append(os.path.join(root, f))
            elif os.path.isfile(p) and p.lower().endswith(SUPPORTED_EXTS):
                collected.append(p)
        return sorted(list(set(collected)))

    def process_file(
        self,
        audio_path: str,
        output_dir: Optional[str] = None,
        basename: Optional[str] = None,
        archive: bool = False,
        speaker_mapping: Optional[Dict[str, str]] = None,
    ) -> PipelineResult:
        start_t = time.time()
        audio_abs = os.path.abspath(os.path.expanduser(audio_path))
        target_out_dir = output_dir or os.path.dirname(audio_abs)
        os.makedirs(target_out_dir, exist_ok=True)

        try:
            # 1. Acoustic ASR
            transcript_file = self.asr.transcribe(
                audio_path=audio_abs,
                output_dir=target_out_dir,
                basename=basename
            )

            # 2. Hotwords correction
            if self.hotwords and os.path.exists(transcript_file):
                self.hotwords.apply_to_file(transcript_file)

            # 3. Cognitive Diarization mapping if provided
            if speaker_mapping and os.path.exists(transcript_file):
                with open(transcript_file, "r", encoding="utf-8") as f:
                    content = f.read()
                updated_content = self.diarizer.apply_mapping(content, speaker_mapping)
                with open(transcript_file, "w", encoding="utf-8") as f:
                    f.write(updated_content)

            # 4. Archiving to cold storage
            arc_res = None
            if archive and self.archiver:
                arc_res = self.archiver.archive_file(audio_abs)

            return PipelineResult(
                audio_file=audio_abs,
                transcript_path=transcript_file,
                archive_result=arc_res,
                elapsed_seconds=time.time() - start_t,
                success=True
            )
        except Exception as e:
            return PipelineResult(
                audio_file=audio_abs,
                elapsed_seconds=time.time() - start_t,
                success=False,
                error=str(e)
            )
