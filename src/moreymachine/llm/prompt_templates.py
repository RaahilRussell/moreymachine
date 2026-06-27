"""Prompt templates for grounded summaries."""

from __future__ import annotations

SYSTEM_INSTRUCTION = (
    "You are summarizing structured basketball ops data. Use only the JSON. "
    "Do not invent facts. If evidence is missing, say it is missing."
)

GM_EXECUTIVE_SUMMARY_PROMPT = (
    f"{SYSTEM_INSTRUCTION}\n\n"
    "Write a concise GM executive summary with these sections: current level, "
    "closest benchmark, top actions, avoid, evidence, and what could be wrong.\n"
    "JSON:\n{packet_json}"
)

