"""summarizer.py · Strategic Executive Synthesis & Action Ledger Generator.
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Any


class StrategicSummarizer:
    """Produces high-density executive digests, strategic trade-off analyses, and action ledgers.
    """

    def __init__(self, project_name: str = "General", default_entities: Optional[List[str]] = None):
        self.project_name = project_name
        self.default_entities = default_entities or []

    def build_summary_prompt(self, transcript_text: str, project_name: Optional[str] = None) -> str:
        proj = project_name or self.project_name
        prompt = (
            "You are an executive chief-of-staff and strategic decision analyst.\n"
            "Review the verbatim meeting transcript below and produce an authoritative executive briefing doc.\n\n"
            "### Required Markdown Structure:\n\n"
            "1. **Frontmatter** (Strict YAML header):\n"
            "   ```yaml\n"
            "   ---\n"
            "   type: meeting_summary\n"
            f"   project: {proj}\n"
            f"   date: {datetime.date.today().isoformat()}\n"
            "   status: active\n"
            "   entities: [List of key stakeholders]\n"
            "   ---\n"
            "   ```\n\n"
            "2. **Executive Takeaway (1-Minute Brief)**: Core alignment, fundamental divergence, and decisive rulings.\n"
            "3. **Meeting Flow & Architecture (Mermaid Diagram)**: Visual timeline of discussion topics.\n"
            "4. **Strategic Debates & Course Corrections**: Deep-dive into technical vs commercial tensions.\n"
            "5. **Product & Commercial Positioning**: Pricing, target market, customer profile, packaging strategy.\n"
            "6. **Organizational & Team Dynamics**: Resourcing, morale, cross-functional dependencies.\n"
            "7. **Action Items Table**: Explicit columns: `| # | Task | Owner | Collaborators | Due Date | Deliverable |`.\n\n"
            "### Verbatim Transcript:\n"
            f"{transcript_text}\n"
        )
        return prompt

    def render_template(
        self,
        title: str,
        takeaway: str,
        mermaid_chart: str,
        debates: List[Dict[str, str]],
        action_items: List[Dict[str, str]],
        entities: Optional[List[str]] = None
    ) -> str:
        """Renders a structured markdown executive summary."""
        ents = entities or self.default_entities
        ents_str = ", ".join(f'"{e}"' for e in ents)

        debates_md = ""
        for d in debates:
            debates_md += f"### {d.get('title', 'Debate')}\n"
            debates_md += f"- **Challenge**: {d.get('challenge', '')}\n"
            debates_md += f"- **Resolution**: {d.get('resolution', '')}\n\n"

        actions_md = "| # | Task | Owner | Collaborators | Due Date | Deliverable |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        for idx, a in enumerate(action_items, 1):
            actions_md += (
                f"| {idx} | {a.get('task', '')} | {a.get('owner', '')} | "
                f"{a.get('collaborators', '-')} | {a.get('due', 'TBD')} | {a.get('deliverable', '')} |\n"
            )

        now_str = datetime.date.today().isoformat()
        md = (
            "---\n"
            "type: meeting_summary\n"
            f"project: \"{self.project_name}\"\n"
            f"date: {now_str}\n"
            "status: active\n"
            f"entities: [{ents_str}]\n"
            "---\n\n"
            f"# {title}\n\n"
            "## 1. Executive Takeaway (1-Minute Brief)\n"
            f"{takeaway}\n\n"
            "## 2. Meeting Flow & Architecture\n"
            "```mermaid\n"
            f"{mermaid_chart.strip()}\n"
            "```\n\n"
            "## 3. Strategic Debates & Course Corrections\n"
            f"{debates_md}\n"
            "## 4. Action Items Table\n"
            f"{actions_md}\n"
        )
        return md
