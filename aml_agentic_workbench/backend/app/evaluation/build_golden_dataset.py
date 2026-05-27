"""CLI for generating versioned golden dataset JSONL artifacts."""

import argparse
import json
from pathlib import Path

from app.evaluation.golden_dataset import build_golden_dataset, write_golden_dataset


def main() -> None:
    """Generate a golden dataset artifact for offline evaluation."""
    parser = argparse.ArgumentParser(description="Generate AML workbench golden evaluation cases.")
    parser.add_argument("--output", type=Path, default=Path("../../artifacts/evaluation/golden_dataset_v1.jsonl"))
    parser.add_argument("--case-limit", type=int, default=100)
    args = parser.parse_args()

    cases = build_golden_dataset(case_limit=args.case_limit)
    write_golden_dataset(cases, args.output)
    print(json.dumps({"case_count": len(cases), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
