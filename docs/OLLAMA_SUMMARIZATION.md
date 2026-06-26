# Ollama Summarization

Ollama is optional. It is not a source of truth for MoreyMachine.

## Allowed Role

Ollama may:

- turn structured JSON into readable strategy prose;
- simplify action-card explanations;
- summarize player profiles;
- summarize benchmark paths;
- summarize manual-review queues.

Ollama may not:

- invent facts;
- infer contracts;
- infer injuries;
- infer transactions;
- infer trade availability;
- infer team intent;
- create unsupported basketball claims;
- override validation.

## Required Prompt Boundary

Every prompt must include:

```text
You are summarizing structured basketball ops data. Use only the JSON. Do not
invent facts. If evidence is missing, say it is missing.
```

## Packets

Narrative packets are structured data objects:

- `gm_summary_packet`
- `team_level_packet`
- `benchmark_path_packet`
- `move_recommendation_packet`
- `player_profile_packet`
- `best_by_need_packet`
- `manual_review_packet`

Each packet contains facts, evidence, confidence, missing-data flags, and source
artifact names.

## Failure Behavior

If Ollama is disabled, not installed, unreachable, times out, or returns
unusable text, the deterministic fallback summary is written. The Streamlit app
should use whichever narrative JSON exists, but every narrative must expose
whether it came from Ollama or fallback code.

## Default Config

`data/manual/llm_config.yml` defaults to:

```yaml
enabled: false
model: llama3.1
base_url: http://localhost:11434
timeout_seconds: 45
max_tokens: 700
temperature: 0.2
cache_enabled: true
```
