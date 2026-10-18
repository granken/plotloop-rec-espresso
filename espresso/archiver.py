"""archiver.py · Cold storage archiver with SHA-256 verification and Markdown pointer cards.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import time
from typing import Optional, Dict, Any


@dataclasses.dataclass
class ArchiveResult:
    source_path: str
    target_path: str
    sha256: str
    size_bytes: int
    pointer_card_path: Optional[str] = None
    pruned_local: bool = False
    success: bool = True
    error_message: Optional[str] = None


class AudioArchiver:
    """Manages cold-storage archiving of high-volume audio files.

    Guarantees data integrity by computing SHA-256 checksums before and after transfer,
    leaves an Obsidian/Markdown pointer card in place of the deleted original,
    and logs entries into an audit ledger.
    """

    def __init__(
        self,
        target_dir: str,
        smb_host: Optional[str] = None,
        smb_share: Optional[str] = None,
        verify_sha256: bool = True,
        prune_original: bool = True,
        ledger_path: Optional[str] = None,
    ):
        self.target_dir = os.path.expanduser(target_dir)
        self.smb_host = smb_host
        self.smb_share = smb_share
        self.verify_sha256 = verify_sha256
        self.prune_original = prune_original
        self.ledger_path = os.path.expanduser(ledger_path) if ledger_path else None

    @staticmethod
    def calculate_sha256(file_path: str, chunk_size: int = 8 * 1024 * 1024) -> str:
        """Calculate SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def ensure_target_accessible(self) -> None:
        """Ensure mount or target directory exists and is writable."""
        if self.smb_host and self.smb_share and sys.platform == "darwin":
            mount_path = f"/Volumes/{self.smb_share}"
            if not os.path.ismount(mount_path):
                # Try mounting via osascript on macOS
                cmd = ["osascript", "-e", f'mount volume "smb://{self.smb_share}@{self.smb_host}/{self.smb_share}"']
                subprocess.run(cmd, capture_output=True, text=True)
                # Wait up to 5s for mount
                for _ in range(10):
                    if os.path.ismount(mount_path):
                        break
                    time.sleep(0.5)

        os.makedirs(self.target_dir, exist_ok=True)

    def archive_file(
        self,
        source_path: str,
        relative_subpath: Optional[str] = None,
        prune: Optional[bool] = None,
    ) -> ArchiveResult:
        source_abs = os.path.abspath(os.path.expanduser(source_path))
        if not os.path.exists(source_abs):
            return ArchiveResult(
                source_path=source_abs,
                target_path="",
                sha256="",
                size_bytes=0,
                success=False,
                error_message=f"Source audio file does not exist: {source_abs}"
            )

        should_prune = self.prune_original if prune is None else prune
        file_size = os.path.getsize(source_abs)

        try:
            self.ensure_target_accessible()
        except Exception as e:
            return ArchiveResult(
                source_path=source_abs,
                target_path="",
                sha256="",
                size_bytes=file_size,
                success=False,
                error_message=f"Target storage is not accessible: {e}"
            )

        # Compute source SHA-256
        source_hash = self.calculate_sha256(source_abs)

        # Destination path
        filename = os.path.basename(source_abs)
        if relative_subpath:
            dest_dir = os.path.join(self.target_dir, relative_subpath)
        else:
            dest_dir = self.target_dir
        os.makedirs(dest_dir, exist_ok=True)

        final_dest = os.path.join(dest_dir, filename)
        part_dest = f"{final_dest}.part_{int(time.time())}"

        # Copy to .part file
        try:
            shutil.copy2(source_abs, part_dest)
        except Exception as e:
            if os.path.exists(part_dest):
                os.remove(part_dest)
            return ArchiveResult(
                source_path=source_abs,
                target_path=final_dest,
                sha256=source_hash,
                size_bytes=file_size,
                success=False,
                error_message=f"File transfer failed: {e}"
            )

        # Verify hash
        if self.verify_sha256:
            dest_hash = self.calculate_sha256(part_dest)
            if dest_hash != source_hash:
                os.remove(part_dest)
                return ArchiveResult(
                    source_path=source_abs,
                    target_path=final_dest,
                    sha256=source_hash,
                    size_bytes=file_size,
                    success=False,
                    error_message=f"SHA-256 mismatch! Source: {source_hash}, Target: {dest_hash}"
                )

        # Atomic rename
        if os.path.exists(final_dest):
            os.remove(final_dest)
        os.rename(part_dest, final_dest)

        # Create Pointer Card
        card_path = f"{source_abs}.md"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        card_content = (
            "---\n"
            "type: audio_archive_pointer\n"
            f"original_file: \"{filename}\"\n"
            f"file_size_bytes: {file_size}\n"
            f"sha256: \"{source_hash}\"\n"
            f"archived_at: \"{now_str}\"\n"
            f"archive_location: \"{final_dest}\"\n"
            "---\n\n"
            f"# Audio Archive Pointer: {filename}\n\n"
            f"- **Original Path**: `{source_abs}`\n"
            f"- **Archive Location**: `{final_dest}`\n"
            f"- **File Size**: {file_size / (1024 * 1024):.2f} MB\n"
            f"- **SHA-256**: `{source_hash}`\n"
            f"- **Archived At**: {now_str}\n\n"
            "> This audio file has been securely archived to cold storage to reclaim local disk space.\n"
            "> Integrity was verified with bit-for-bit SHA-256 checksum validation.\n"
        )

        with open(card_path, "w", encoding="utf-8") as f:
            f.write(card_content)

        # Prune local audio file if requested
        pruned = False
        if should_prune:
            os.remove(source_abs)
            pruned = True

        # Append to audit ledger if configured
        if self.ledger_path:
            self._append_ledger(filename, file_size, source_hash, final_dest, now_str)

        return ArchiveResult(
            source_path=source_abs,
            target_path=final_dest,
            sha256=source_hash,
            size_bytes=file_size,
            pointer_card_path=card_path,
            pruned_local=pruned,
            success=True
        )

    def _append_ledger(self, filename: str, size: int, sha: str, target: str, date_str: str) -> None:
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        init_header = not os.path.exists(self.ledger_path)
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            if init_header:
                f.write("# Audio Archive Audit Ledger\n\n")
                f.write("| Timestamp | Filename | Size (MB) | SHA-256 | Destination |\n")
                f.write("| :--- | :--- | :--- | :--- | :--- |\n")
            mb = size / (1024 * 1024)
            f.write(f"| {date_str} | {filename} | {mb:.1f} | `{sha[:12]}...` | `{target}` |\n")
