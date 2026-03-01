"""CLI for running LLM Council and exporting markdown outputs."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import json

from .council import run_full_council
from .config import COUNCIL_ALGORITHM, LLM_PROVIDER, COUNCIL_MODELS, CHAIRMAN_MODEL


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
    return f"""# LLM Council Run

- Generated: {timestamp}
- Provider: `{LLM_PROVIDER}`
- Algorithm: `{metadata.get('algorithm', COUNCIL_ALGORITHM)}`
- Council models: `{', '.join(COUNCIL_MODELS)}`
- Chairman: `{CHAIRMAN_MODEL}`

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


async def _run(args: argparse.Namespace) -> int:
    prompt = _read_prompt(args)
    stage1, stage2, stage3, metadata = await run_full_council(prompt, algorithm=args.algorithm)

    if args.output:
        output_path = Path(args.output)
    else:
        slug = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        output_path = Path(f"data/council-runs/{slug}.md")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_to_markdown(prompt, stage1, stage2, stage3, metadata))
    print(f"Wrote markdown report: {output_path}")

    if args.print_final:
        print("\n=== FINAL RESPONSE ===\n")
        print(stage3.get("response", ""))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LLM Council from CLI and export markdown")
    parser.add_argument("--prompt", type=str, help="Prompt text")
    parser.add_argument("--input-file", type=str, help="Path to text/markdown file for prompt")
    parser.add_argument("--algorithm", type=str, default=None, help="peer_review|consensus_only|chairman_only")
    parser.add_argument("--output", type=str, default=None, help="Output markdown path")
    parser.add_argument("--print-final", action="store_true", help="Print final chairman response")

    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
