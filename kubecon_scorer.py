#!/usr/bin/env python3
"""KubeCon EU 2026 Event Scorer - CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ics_parser import download_ics, filter_scorable, parse_ics
from providers import get_provider
from report import generate_report
from scorer import load_profile, score_all_events


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score KubeCon EU 2026 events against your profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s -p profiles/platform_engineer.yaml --provider claude
  %(prog)s -p profiles/platform_engineer.yaml --provider openai
  %(prog)s -p profiles/platform_engineer.yaml --dry-run
  %(prog)s -p profiles/platform_engineer.yaml --provider gemini --min-score 60
""",
    )
    parser.add_argument(
        "-p", "--profile", required=True, help="Path to YAML profile"
    )
    parser.add_argument(
        "--provider",
        choices=["claude", "openai", "gemini"],
        default="claude",
        help="AI provider (default: claude)",
    )
    parser.add_argument("--model", help="Override default model for the provider")
    parser.add_argument("--api-key", help="API key (or use env var)")
    parser.add_argument(
        "--batch-size", type=int, default=12, help="Events per API call (default: 12)"
    )
    parser.add_argument("-o", "--output", help="Output HTML path")
    parser.add_argument(
        "--min-score", type=int, default=0, help="Minimum score to include in report"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Force re-download ICS"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Skip score cache"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse ICS and show stats without scoring",
    )
    parser.add_argument(
        "--ics-url",
        default="https://kccnceu2026.sched.com/all.ics",
        help="Custom ICS URL",
    )

    args = parser.parse_args()

    # Load profile
    print(f"Loading profile: {args.profile}")
    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"  Profile: {profile.name} ({profile.role})")

    # Download ICS
    print(f"Downloading schedule...")
    try:
        ics_path = download_ics(
            url=args.ics_url, force_refresh=args.refresh
        )
    except Exception as e:
        print(f"Error downloading ICS: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"  ICS cached at: {ics_path}")

    # Parse events
    print("Parsing events...")
    all_events = parse_ics(ics_path)
    print(f"  Total events in ICS: {len(all_events)}")

    events = filter_scorable(all_events, profile.exclude_categories)
    print(f"  Scorable events: {len(events)}")

    if not events:
        print("No scorable events found.", file=sys.stderr)
        sys.exit(1)

    # Dry run stats
    if args.dry_run:
        _print_dry_run_stats(all_events, events)
        return

    # Score events
    print("Scoring events...")
    provider = get_provider(args.provider, model=args.model, api_key=args.api_key)
    scored = score_all_events(
        events,
        profile,
        provider,
        ics_path,
        batch_size=args.batch_size,
        no_cache=args.no_cache,
    )

    # Generate report
    print("Generating report...")
    output = generate_report(
        scored,
        profile,
        provider_name=f"{provider.name} ({provider.model})",
        output_path=args.output,
        min_score=args.min_score,
    )
    print(f"  Report saved to: {output}")

    # Summary
    _print_summary(scored)


def _print_dry_run_stats(all_events, scorable_events):
    """Print detailed stats without scoring."""
    from collections import Counter

    print("\n--- Dry Run Stats ---")
    print(f"Total events:    {len(all_events)}")
    print(f"Scorable events: {len(scorable_events)}")
    print(f"Filtered out:    {len(all_events) - len(scorable_events)}")

    # Events by day
    from collections import defaultdict
    days = defaultdict(int)
    for e in scorable_events:
        days[e.day_display] += 1
    print("\nEvents by day:")
    for day, count in sorted(days.items()):
        print(f"  {day}: {count}")

    # Categories
    cats = Counter()
    for e in scorable_events:
        for c in e.categories:
            cats[c] += 1
    if cats:
        print("\nTop categories:")
        for cat, count in cats.most_common(15):
            print(f"  {cat}: {count}")

    # Duration stats
    durations = [e.duration_minutes for e in scorable_events]
    if durations:
        print(f"\nDuration range: {min(durations)}-{max(durations)} min")
        print(f"Average duration: {sum(durations) // len(durations)} min")


def _print_summary(scored):
    """Print scoring summary."""
    must = sum(1 for se in scored if se.score >= 85)
    rec = sum(1 for se in scored if 70 <= se.score < 85)
    consider = sum(1 for se in scored if 50 <= se.score < 70)
    low = sum(1 for se in scored if se.score < 50)
    avg = sum(se.score for se in scored) // len(scored) if scored else 0

    print(f"\n--- Scoring Summary ---")
    print(f"Must-Attend (85+): {must}")
    print(f"Recommended (70-84): {rec}")
    print(f"Consider (50-69): {consider}")
    print(f"Low Priority (<50): {low}")
    print(f"Average Score: {avg}")

    if must > 0:
        print(f"\nTop sessions:")
        for se in sorted(scored, key=lambda x: -x.score)[:5]:
            print(f"  [{se.score}] {se.event.summary}")


if __name__ == "__main__":
    main()
