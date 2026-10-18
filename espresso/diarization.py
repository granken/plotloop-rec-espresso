"""diarization.py · Cognitive Speaker Diarization & Identity Resolution.
"""
from __future__ import annotations

import dataclasses
import re
from typing import Dict, List, Optional, Tuple


@dataclasses.dataclass
class TranscriptTurn:
    speaker: str
    start_time: Optional[str]
    end_time: Optional[str]
    content: str
    raw_header: str


class CognitiveDiarizer:
    """Bridges acoustic speaker clusters (Speaker 1, 2) and cognitive identities.

    Extracts turns, builds context prompts for LLM resolution based on conversation clues,
    and applies final resolved speaker mappings.
    """

    TURN_PATTERN = re.compile(
        r"^(?:\*\*\[([\d:.]+)\s*-\s*([\d:.]+)\]\s*)?([^\n:：]+?)[:：]\s*(.*)$",
        re.MULTILINE
    )

    def __init__(self, speaker_map: Optional[Dict[str, str]] = None):
        self.speaker_map: Dict[str, str] = speaker_map or {}

    def parse_turns(self, transcript_text: str) -> List[TranscriptTurn]:
        """Parses standard markdown transcript into structured speaker turns."""
        turns: List[TranscriptTurn] = []
        for line in transcript_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            match = self.TURN_PATTERN.match(line_str)
            if match:
                start_t, end_t, spk, content = match.groups()
                clean_spk = spk.replace("*", "").strip()
                turns.append(TranscriptTurn(
                    speaker=clean_spk,
                    start_time=start_t,
                    end_time=end_t,
                    content=content.strip(),
                    raw_header=line_str[:line_str.find(content)].strip()
                ))
            elif turns:
                # Continuation of previous turn
                turns[-1].content += f"\n{line_str}"
        return turns

    def get_speaker_summary(self, transcript_text: str) -> Dict[str, Dict[str, int]]:
        """Summarizes turn count and approximate word count per speaker."""
        turns = self.parse_turns(transcript_text)
        stats: Dict[str, Dict[str, int]] = {}
        for turn in turns:
            spk = turn.speaker
            if spk not in stats:
                stats[spk] = {"turns": 0, "chars": 0}
            stats[spk]["turns"] += 1
            stats[spk]["chars"] += len(turn.content)
        return stats

    def build_resolution_prompt(self, transcript_text: str, roster_info: str) -> str:
        """Constructs an LLM prompt to map acoustic speaker tags to real identities."""
        summary = self.get_speaker_summary(transcript_text)
        summary_lines = [f"- **{spk}**: {meta['turns']} turns, ~{meta['chars']} chars" for spk, meta in summary.items()]

        prompt = (
            "You are an expert executive meeting analyst and speaker identification specialist.\n"
            "Analyze the meeting transcript below and resolve anonymous speaker tags (e.g. 'Speaker 1', 'Speaker 2') "
            "to their real names and organizational roles using context clues, linguistic patterns, and the provided roster.\n\n"
            "### Attendee Roster & Background Clues:\n"
            f"{roster_info}\n\n"
            "### Detected Acoustic Speakers:\n"
            f"{chr(10).join(summary_lines)}\n\n"
            "### Task Instructions:\n"
            "1. Infer who each speaker is based on who opens the meeting, who reports progress, specific domain terminology used, and tone.\n"
            "2. Provide a JSON mapping of each speaker tag to their identified name and title, with your reasoning:\n"
            "   ```json\n"
            "   {\n"
            "     \"Speaker 1\": {\"name\": \"Alice\", \"role\": \"VP of Engineering\", \"confidence\": 0.95, \"evidence\": \"Introduced agenda...\"},\n"
            "     \"Speaker 2\": {\"name\": \"Bob\", \"role\": \"Lead Architect\", \"confidence\": 0.90, \"evidence\": \"Discussed GPU benchmarks...\"}\n"
            "   }\n"
            "   ```\n"
            "3. Output the fully resolved transcript with format: `**[HH:MM:SS - HH:MM:SS] Name (Role)**: content`.\n\n"
            "### Raw Transcript Excerpt:\n"
            f"{transcript_text[:4000]}\n"
        )
        return prompt

    def apply_mapping(self, transcript_text: str, mapping: Optional[Dict[str, str]] = None) -> str:
        """Replaces anonymous speaker tags with resolved identities."""
        active_map = mapping or self.speaker_map
        if not active_map:
            return transcript_text

        result_lines: List[str] = []
        for line in transcript_text.splitlines():
            modified = line
            for old_spk, new_spk in active_map.items():
                # Match patterns like: **Speaker 1**: or [00:01] Speaker 1: or Speaker 1:
                pattern = re.compile(rf"(^|\*|\[|\s)({re.escape(old_spk)})(?=\*|\:|：|\s|\])")
                modified = pattern.sub(rf"\g<1>{new_spk}", modified)
            result_lines.append(modified)
        return "\n".join(result_lines)
