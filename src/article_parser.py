#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Article Parser module for processing JSON/JSONL datasets.

This module extracts articles from structured datasets (JSON/JSONL format)
and saves them as individual text files with formatted sections.

Usage:
    python -m src.article_parser \\
        --in_file data.json \\
        --out_dir ./data/articles \\
        --overwrite
"""

import argparse
import json
import os
from typing import Any, Dict, List, Tuple


def read_json_or_jsonl(path: str) -> List[Dict[str, Any]]:
    """
    Read data from JSON or JSONL file.

    Args:
        path: Path to input file (.json or .jsonl)

    Returns:
        List of records

    Raises:
        ValueError: If file format is not supported or JSON is not a list
    """
    path = path.strip()

    if path.endswith(".jsonl"):
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return obj
        raise ValueError("JSON must be a list of records.")

    raise ValueError("Input must be .json or .jsonl")


def split_passage_and_options(passage: str) -> Tuple[str, str]:
    """
    Split passage text from options section.

    Looks for [OPTIONS] markers and separates the main article text
    from the multiple choice options.

    Args:
        passage: Combined passage text

    Returns:
        Tuple of (article_text, options_block)
    """
    if passage is None:
        return "", ""

    s = passage.strip()

    # Try different marker formats
    marker = "\n[OPTIONS]\n"
    if marker in s:
        article, opts = s.split(marker, 1)
        article = article.rstrip()
        opts = "[OPTIONS]\n" + opts.strip()
        return article, opts

    marker2 = "\n\n[OPTIONS]\n"
    if marker2 in s:
        article, opts = s.split(marker2, 1)
        article = article.rstrip()
        opts = "[OPTIONS]\n" + opts.strip()
        return article, opts

    return s, ""


def format_options_from_dict(options: Dict[str, Any]) -> str:
    """
    Format options dictionary into text block.

    Args:
        options: Dictionary with keys A, B, C, D

    Returns:
        Formatted options block string
    """
    if not isinstance(options, dict):
        return ""

    options_lines = []
    for k in ["A", "B", "C", "D"]:
        if k in options and isinstance(options[k], str) and options[k].strip():
            options_lines.append(f"{k}. {options[k].strip()}")

    if not options_lines:
        return ""

    return "[OPTIONS]\n" + "\n".join(options_lines) + "\n"


def safe_write(path: str, content: str):
    """
    Write content to file, creating directories as needed.

    Args:
        path: Output file path
        content: Content to write
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Parse JSON/JSONL dataset and extract articles to individual files"
    )
    ap.add_argument(
        "--in_file",
        required=True,
        help="Path to input .json or .jsonl file"
    )
    ap.add_argument(
        "--out_dir",
        required=True,
        help="Output directory for article files"
    )
    ap.add_argument(
        "--ext",
        default=".txt",
        help="Output file extension (default: .txt)"
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files"
    )
    args = ap.parse_args()

    rows = read_json_or_jsonl(args.in_file)
    if not rows:
        raise RuntimeError("Empty input file.")

    os.makedirs(args.out_dir, exist_ok=True)

    index: Dict[str, Dict[str, Any]] = {}
    written = 0
    skipped = 0
    missing = 0

    for r in rows:
        sid = str(r.get("id", "")).strip()
        if not sid:
            missing += 1
            continue

        passage = r.get("passage", "")
        article_text, passage_options_block = split_passage_and_options(passage)

        json_options_block = format_options_from_dict(r.get("options", {}))
        options_block = json_options_block if json_options_block else passage_options_block

        question = str(r.get("question", "")).strip()
        if "\nOPTIONS:\n" in question:
            question = question.split("\nOPTIONS:\n")[0].strip()

        # Remove duplicate lines in question
        question_lines = list(dict.fromkeys(
            [line.strip() for line in question.splitlines() if line.strip()]
        ))
        question = "\n".join(question_lines)

        out_path = os.path.join(args.out_dir, f"{sid}{args.ext}")
        if (not args.overwrite) and os.path.exists(out_path):
            skipped += 1
            continue

        # Build output content
        body_parts = []
        body_parts.append(f"[ID]\n{sid}\n")
        body_parts.append(f"[ARTICLE]\n{article_text.strip()}\n")
        if question:
            body_parts.append(f"[QUESTION]\n{question}\n")
        if options_block:
            body_parts.append(f"{options_block.strip()}\n")

        body = "\n".join(body_parts)

        # Remove duplicate [QUESTION] blocks
        while "\n[QUESTION]\n" in body and body.count("\n[QUESTION]\n") > 1:
            first_occur = body.find("\n[QUESTION]\n")
            next_occur = body.find("\n[QUESTION]\n", first_occur + 1)
            if next_occur != -1:
                end_question = body.find("\n[", next_occur + 1)
                if end_question == -1:
                    end_question = len(body)
                body = body[:next_occur] + body[end_question:]

        safe_write(out_path, body)
        written += 1

        index[sid] = {
            "file": os.path.abspath(out_path),
            "article_chars": len(article_text),
            "question_chars": len(question),
            "has_options": bool(options_block),
            "total_chars": len(body),
        }

    # Write index file
    index_path = os.path.join(args.out_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "input": os.path.abspath(args.in_file),
                "out_dir": os.path.abspath(args.out_dir),
                "count_in_file": len(rows),
                "written": written,
                "skipped": skipped,
                "missing_id": missing,
                "items": index,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Loaded: {len(rows)} records")
    print(f"Written: {written}, Skipped: {skipped}, Missing id: {missing}")
    print(f"Index: {index_path}")


if __name__ == "__main__":
    main()
