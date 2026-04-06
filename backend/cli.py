"""CLI for running LLM Council and exporting markdown outputs."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import json
import sys

from .council import run_full_council
from .config import get_config

ALGORITHM_CHOICES = [
    "peer_review",
    "consensus_only",
    "chairman_only",
    "red_team",
    "audience_split",
    "claim_evidence",
]


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt.strip()
    if args.input_file:
        return Path(args.input_file).read_text().strip()
    raise ValueError("Provide --prompt or --input-file")


def _fmt_stage1(stage1: list[dict]) -> str:
    if not stage1:
        return "_No stage1 responses._"
    lines = []
    for i, r in enumerate(stage1, start=1):
        lines.append(f"### {i}. {r.get('model','unknown')}")
        lines.append("")
        lines.append(r.get("response", "").strip() or "_Empty response_")
        lines.append("")
    return "\n".join(lines)


def _fmt_stage2(stage2: list[dict]) -> str:
    if not stage2:
        return "_Stage2 skipped by algorithm._"
    lines = []
    for i, r in enumerate(stage2, start=1):
        lines.append(f"### {i}. Reviewer: {r.get('model','unknown')}")
        lines.append("")
        lines.append(r.get("ranking", "").strip() or "_Empty ranking_")
        lines.append("")
    return "\n".join(lines)


def _to_markdown(prompt: str, stage1: list[dict], stage2: list[dict], stage3: dict, metadata: dict) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cfg = get_config()
    return f"""# LLM Council Run

- Generated: {timestamp}
- Provider: `{cfg['llm_provider']}`
- Algorithm: `{metadata.get('algorithm', cfg['council_algorithm'])}`
- Council models: `{', '.join(cfg['council_models'])}`
- Chairman: `{cfg['chairman_model']}`

## Prompt

{prompt}

## Stage 1 - First Opinions

{_fmt_stage1(stage1)}

## Stage 2 - Peer Review Rankings

{_fmt_stage2(stage2)}

## Stage 3 - Chairman Synthesis

{stage3.get('response','').strip() if stage3 else '_No final response_'}

## Metadata

```json
{json.dumps(metadata, indent=2)}
```
"""


def _build_result(
    prompt: str,
    stage1: list[dict],
    stage2: list[dict],
    stage3: dict,
    metadata: dict,
    *,
    output_path: Path | None = None,
) -> dict:
    """Build structured CLI output for automation-friendly consumption."""
    cfg = get_config()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "success": not _run_failed(stage3),
        "generated_at": generated_at,
        "provider": cfg["llm_provider"],
        "algorithm": metadata.get("algorithm", cfg["council_algorithm"]),
        "council_models": cfg["council_models"],
        "chairman_model": cfg["chairman_model"],
        "prompt": prompt,
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "metadata": metadata,
        "output_path": str(output_path) if output_path else None,
    }


def _run_failed(stage3: dict | None) -> bool:
    """Return True when the CLI run should be treated as a failure."""
    if not stage3:
        return True

    model = stage3.get("model")
    response = (stage3.get("response") or "").strip()
    return model == "error" or response == "Error: Unable to generate final synthesis."


async def _run(args: argparse.Namespace) -> int:
    prompt = _read_prompt(args)
    stage1, stage2, stage3, metadata = await run_full_council(prompt, algorithm=args.algorithm)

    output_path = None
    if args.output:
        output_path = Path(args.output)
    elif not args.json:
        slug = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        output_path = Path(f"data/council-runs/{slug}.md")

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_to_markdown(prompt, stage1, stage2, stage3, metadata))
        if not args.json:
            print(f"Wrote markdown report: {output_path}")

    result = _build_result(prompt, stage1, stage2, stage3, metadata, output_path=output_path)

    if args.json:
        print(json.dumps(result, indent=2))
    elif args.print_final:
        print("\n=== FINAL RESPONSE ===\n")
        print(stage3.get("response", ""))

    return 1 if _run_failed(stage3) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LLM Council from CLI and export markdown")
    parser.add_argument("--prompt", type=str, help="Prompt text")
    parser.add_argument("--input-file", type=str, help="Path to text/markdown file for prompt")
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=ALGORITHM_CHOICES,
        default=None,
        help="Council algorithm to run",
    )
    parser.add_argument("--output", type=str, default=None, help="Output markdown path")
    parser.add_argument("--json", action="store_true", help="Print structured JSON to stdout")
    parser.add_argument("--print-final", action="store_true", help="Print final chairman response")

    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
