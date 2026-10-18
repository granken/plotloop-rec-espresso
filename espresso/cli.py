"""cli.py · Command-Line Interface for PlotLoop Rec-Espresso.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from espresso import __version__
    from espresso.asr import VolcengineASR, WhisperASR, MockASR
    from espresso.hotwords import HotwordsReplacer
    from espresso.archiver import AudioArchiver
    from espresso.pipeline import EspressoPipeline
else:
    from . import __version__
    from .asr import VolcengineASR, WhisperASR, MockASR
    from .hotwords import HotwordsReplacer
    from .archiver import AudioArchiver
    from .pipeline import EspressoPipeline



def print_banner():
    banner = rf"""
  ╔══════════════════════════════════════════════════════════════════╗
  ║   ☕ PlotLoop Rec-Espresso  v{__version__:<33}║
  ║   Lightning Audio Diarization, Executive Digest & Archiving      ║
  ╚══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def cmd_run(args):
    pipeline = None
    if args.config and os.path.exists(args.config):
        pipeline = EspressoPipeline.from_config_file(args.config)
    else:
        # Build from CLI flags
        if args.provider == "whisper":
            asr = WhisperASR()
        elif args.provider == "mock":
            asr = MockASR()
        else:
            asr = VolcengineASR()

        hotwords = None
        if args.glossary and os.path.exists(args.glossary):
            hotwords = HotwordsReplacer.from_file(args.glossary)

        archiver = None
        if args.archive:
            archiver = AudioArchiver(
                target_dir=args.archive_dir or "~/Backups/audio-archive",
                verify_sha256=True,
                prune_original=not args.keep_local,
            )

        pipeline = EspressoPipeline(
            asr_adapter=asr,
            hotwords_replacer=hotwords,
            archiver=archiver
        )

    files = pipeline.collect_audio_files(args.inputs)
    if not files:
        print("✗ No supported audio files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(files)} audio file(s):")
    total_size = sum(os.path.getsize(f) for f in files)
    for f in files:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  • {f} ({size_mb:.1f} MB)")
    print(f"Total volume: {total_size / (1024 * 1024):.1f} MB\n")

    if args.dry_run:
        print("[Dry Run] Simulation completed. No audio processed or archived.")
        return

    results = []
    for idx, audio_path in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] Processing: {os.path.basename(audio_path)} ...")
        res = pipeline.process_file(
            audio_path=audio_path,
            output_dir=args.output_dir,
            basename=args.basename if len(files) == 1 else None,
            archive=args.archive
        )
        if res.success:
            print(f"  ✓ Transcribed: {res.transcript_path} ({res.elapsed_seconds:.1f}s)")
            if res.archive_result and res.archive_result.success:
                print(f"  ✓ Cold archived: {res.archive_result.target_path}")
                if res.archive_result.pointer_card_path:
                    print(f"  ✓ Pointer card: {res.archive_result.pointer_card_path}")
        else:
            print(f"  ✗ Failed: {res.error}", file=sys.stderr)
        results.append(res)

    print("\n✓ Pipeline execution complete.")


def cmd_archive(args):
    """Standalone cold storage archiver command."""
    archiver = AudioArchiver(
        target_dir=args.target_dir,
        smb_host=args.smb_host,
        smb_share=args.smb_share,
        verify_sha256=not args.no_verify,
        prune_original=not args.keep_local,
        ledger_path=args.ledger
    )

    files = EspressoPipeline.collect_audio_files(args.inputs)
    if not files:
        print("✗ No audio files found to archive.", file=sys.stderr)
        sys.exit(1)

    print(f"Archiving {len(files)} file(s) to {args.target_dir}...")
    for idx, f in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] Archiving {os.path.basename(f)} ...")
        res = archiver.archive_file(f)
        if res.success:
            status = "Local audio pruned" if res.pruned_local else "Local audio kept"
            print(f"  ✓ Archived: {res.target_path} (SHA-256: {res.sha256[:12]}..., {status})")
        else:
            print(f"  ✗ Error: {res.error_message}", file=sys.stderr)


def cmd_hotwords(args):
    """Standalone hotwords replacement command."""
    if not os.path.exists(args.glossary):
        print(f"✗ Glossary file not found: {args.glossary}", file=sys.stderr)
        sys.exit(1)

    replacer = HotwordsReplacer.from_file(args.glossary)
    for target in args.files:
        if os.path.exists(target):
            count = replacer.apply_to_file(target)
            print(f"✓ Updated {target} ({count} lines modified)")
        else:
            print(f"⚠ File not found: {target}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        prog="plotloop-espresso",
        description="PlotLoop Rec-Espresso · Lightning Audio Extraction & Archiving Pipeline"
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Run pipeline
    p_run = subparsers.add_parser("run", help="Run end-to-end transcription & digest pipeline")
    p_run.add_argument("inputs", nargs="+", help="Audio file(s) or folder(s)")
    p_run.add_argument("-c", "--config", help="Path to config.json")
    p_run.add_argument("-o", "--output-dir", help="Directory for output transcripts")
    p_run.add_argument("-b", "--basename", help="Custom base name (single file only)")
    p_run.add_argument("--provider", choices=["volcengine", "whisper", "mock"], default="volcengine", help="ASR Engine")
    p_run.add_argument("--glossary", help="Path to domain hotwords glossary")
    p_run.add_argument("--archive", action="store_true", help="Archive to cold storage upon completion")
    p_run.add_argument("--archive-dir", help="Cold storage destination directory")
    p_run.add_argument("--keep-local", action="store_true", help="Preserve local audio file after archiving")
    p_run.add_argument("--dry-run", action="store_true", help="Dry run without processing")

    # Standalone archive
    p_arc = subparsers.add_parser("archive", help="Standalone cold-storage audio archiver")
    p_arc.add_argument("inputs", nargs="+", help="Audio file(s) or folder(s) to archive")
    p_arc.add_argument("-t", "--target-dir", required=True, help="Destination directory (NAS or backup volume)")
    p_arc.add_argument("--smb-host", help="SMB host (e.g. nas.local)")
    p_arc.add_argument("--smb-share", help="SMB share name")
    p_arc.add_argument("--ledger", help="Markdown audit ledger file path")
    p_arc.add_argument("--keep-local", action="store_true", help="Keep local original file")
    p_arc.add_argument("--no-verify", action="store_true", help="Skip SHA-256 integrity verification")

    # Standalone hotwords
    p_hw = subparsers.add_parser("hotwords", help="Apply hotwords glossary to markdown transcripts")
    p_hw.add_argument("-g", "--glossary", required=True, help="Glossary JSON or Markdown file")
    p_hw.add_argument("files", nargs="+", help="Markdown transcript files to correct")

    args = parser.parse_args()

    if not args.subcommand:
        # Default to 'run' if positional inputs are given, or print help
        parser.print_help()
        sys.exit(0)

    print_banner()

    if args.subcommand == "run":
        cmd_run(args)
    elif args.subcommand == "archive":
        cmd_archive(args)
    elif args.subcommand == "hotwords":
        cmd_hotwords(args)


if __name__ == "__main__":
    main()
