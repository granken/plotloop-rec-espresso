"""hotwords.py · Hotwords and domain-specific terminology correction.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional


class HotwordsReplacer:
    """Corrects mistranscribed homophones, domain jargon, and roster names."""

    def __init__(self, replacements: Optional[Dict[str, str]] = None):
        self.replacements: Dict[str, str] = replacements or {}

    @classmethod
    def from_file(cls, path: str) -> "HotwordsReplacer":
        """Load replacements from JSON, Markdown table, or YAML file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Glossary file not found: {path}")

        replacements: Dict[str, str] = {}
        _, ext = os.path.splitext(path.lower())

        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    replacements.update(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "wrong" in item and "correct" in item:
                            replacements[item["wrong"]] = item["correct"]
        elif ext in (".md", ".txt"):
            # Supports Markdown table format: | Wrong | Correct | or bullet lines: - Wrong -> Correct
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Table row: | 纳米Work | 纳米工作 |
                    if line.startswith("|") and line.endswith("|"):
                        parts = [p.strip() for p in line.split("|")[1:-1]]
                        if len(parts) >= 2 and parts[0] != "---" and parts[0] != "原词":
                            replacements[parts[0]] = parts[1]
                    # Arrow syntax: wrong -> correct
                    elif "->" in line:
                        wrong, correct = line.split("->", 1)
                        replacements[wrong.strip()] = correct.strip()
                    # Colon syntax: wrong: correct
                    elif ":" in line and not line.startswith("#"):
                        wrong, correct = line.split(":", 1)
                        replacements[wrong.strip()] = correct.strip()

        return cls(replacements)

    def add_rule(self, wrong: str, correct: str) -> None:
        self.replacements[wrong] = correct

    def apply(self, text: str) -> str:
        """Applies all replacements sequentially, sorted by length descending to prevent partial match conflicts."""
        if not self.replacements:
            return text

        # Sort keys by length descending so longer phrases match before substrings
        sorted_keys = sorted(self.replacements.keys(), key=len, reverse=True)
        result = text
        for wrong in sorted_keys:
            correct = self.replacements[wrong]
            if wrong and wrong in result:
                result = result.replace(wrong, correct)
        return result

    def apply_to_file(self, file_path: str) -> int:
        """Applies replacements in-place to a text file. Returns count of modified lines."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        modified_count = 0
        new_lines: List[str] = []
        for line in lines:
            new_line = self.apply(line)
            if new_line != line:
                modified_count += 1
            new_lines.append(new_line)

        if modified_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

        return modified_count
