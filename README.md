# KubeCon EU 2026 Event Scorer

Score and rank KubeCon + CloudNativeCon EU 2026 sessions (March 23-26, Amsterdam) against your personal profile using AI. Generates a self-contained HTML report with ranked events grouped by day and timeslot, with conflict detection.

## How It Works

1. Downloads the full conference schedule from sched.com (ICS format, ~500 events)
2. Filters out non-session events (registration, breaks, meals)
3. Sends events in batches to an AI provider with your profile context
4. Each event is scored 0-100 across three dimensions:
   - **Role Relevance** (0-35): How relevant to your job
   - **Topic Alignment** (0-35): How well it matches your interests
   - **Strategic Value** (0-30): Unique insights and actionable takeaways
5. Generates an interactive HTML report you can open in any browser

## Quick Start

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Dry run - verify ICS parsing, no API key needed
python3 kubecon_scorer.py -p profiles/platform_engineer.yaml --dry-run

# Score with Claude (set ANTHROPIC_API_KEY first)
export ANTHROPIC_API_KEY=sk-...
python3 kubecon_scorer.py -p profiles/platform_engineer.yaml --provider claude

# Score with OpenAI
export OPENAI_API_KEY=sk-...
python3 kubecon_scorer.py -p profiles/platform_engineer.yaml --provider openai

# Score with Gemini
export GOOGLE_API_KEY=...
python3 kubecon_scorer.py -p profiles/platform_engineer.yaml --provider gemini
```

The report is saved to `output/kubecon_<profile_name>.html`.

## CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --profile` | Path to YAML profile (required) | - |
| `--provider` | AI provider: `claude`, `openai`, `gemini` | `claude` |
| `--model` | Override the provider's default model | Provider default |
| `--api-key` | API key (alternative to env var) | - |
| `--batch-size` | Events per API call | `12` |
| `-o, --output` | Custom output HTML path | `output/kubecon_<name>.html` |
| `--min-score` | Only include events scoring at or above this | `0` |
| `--refresh` | Force re-download the ICS feed | `false` |
| `--no-cache` | Skip score cache, re-score everything | `false` |
| `--dry-run` | Parse ICS and show stats, no scoring | `false` |

## Creating a Profile

Copy `profiles/example.yaml` and customize it. Key fields:

```yaml
name: "Your Name"
role: "Your Job Title"
organization: "Your Company"
experience_level: "advanced"  # beginner | intermediate | advanced | expert

interests:
  primary:
    - "Platform engineering"
    - "Kubernetes operators"
  secondary:
    - "Observability"
    - "Security"

priorities:
  - "Evaluate tools for our internal developer platform"
  - "Learn multi-tenant Kubernetes patterns"

preferences:
  prefer_hands_on: true       # Boost workshops and labs
  prefer_deep_dives: true     # Boost advanced talks
  avoid_vendor_pitches: true  # Penalize marketing-heavy sessions

context: "We run 50+ clusters, migrating to GitOps..."
```

See `profiles/example.yaml` for full documentation of all fields.

### Tip: Use AI to generate your profile

Instead of writing your profile from scratch, ask an AI assistant (like Claude Code, ChatGPT, or Copilot) to generate it for you. Give it a few bullet points about yourself and it can fill in the rest:

> "I'm a DevOps / cloud native engineer at Acme Corp. My main interests are Crossplane, AI on Kubernetes, and platform engineering. I'm advanced level and prefer hands-on deep dives. Generate a kubecon scorer YAML profile for me."

The AI can pull from your GitHub repos, job title, and tech stack to create a well-rounded profile with relevant interests, priorities, and context. Much faster than filling in every field manually.

## Report Features

- **Day tabs**: Navigate between co-located events (Mar 23) and main conference days (Mar 24-26)
- **Score threshold slider**: Filter events by minimum score in real time
- **Text search**: Search event titles
- **Category filter**: Filter by session category
- **Conflict detection**: Overlapping sessions are flagged with conflict badges
- **Score breakdown bars**: Visual breakdown of role relevance, topic alignment, and strategic value
- **Expandable descriptions**: Click to reveal full session descriptions
- **Direct links**: Each event links to its sched.com page
- **Fully portable**: Single HTML file with inline CSS/JS, works offline

## Score Tiers

| Score | Color | Meaning |
|-------|-------|---------|
| 85-100 | Green | Must-attend |
| 70-84 | Blue | Recommended |
| 50-69 | Amber | Consider |
| 30-49 | Gray | Low priority |
| 0-29 | Light gray | Skip |

## Caching

- The ICS feed is cached for 24 hours in `cache/events.ics`
- Scores are cached per profile + ICS content hash in `cache/scores_<profile>_<hash>.json`
- Use `--refresh` to re-download the ICS feed
- Use `--no-cache` to force re-scoring

## AI Providers

| Provider | Default Model | Env Var | SDK |
|----------|--------------|---------|-----|
| Claude | `claude-opus-4-6` | `ANTHROPIC_API_KEY` | `anthropic` |
| OpenAI | `gpt-5.2` | `OPENAI_API_KEY` | `openai` |
| Gemini | `gemini-3.0-pro` | `GOOGLE_API_KEY` | `google-genai` |

Override the model with `--model`, e.g. `--provider claude --model claude-sonnet-4-20250514` for a cheaper/faster option.

## Requirements

- Python 3.10+
- An API key for at least one provider
