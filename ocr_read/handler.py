#!/usr/bin/env python3
"""OCR tool handler for Mavambo.

Mavambo contract:
  - stdin carries ONE JSON envelope: {"tool", "arguments": {...}, "cwd": "..."}
  - stdout must carry ONE JSON object AND the process must exit 0:
        {"result": <value>}   on success
        {"error":  "<why>"}   on failure   (never signal failure with exit code)
  Mavambo reads the exit code first; any nonzero exit is reported as a crash and
  stdout is never parsed. Failures are the "error" key, not sys.exit(1).
"""

import sys
import os
import json
import pathlib


def fail(message):
    json.dump({"error": message}, sys.stdout)
    raise SystemExit(0)          # exit 0: the error travels in the JSON


def resolve(root, name):
    """A path inside the project, or None (rejects .. and absolute paths)."""
    candidate = pathlib.Path(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        target = (root / candidate).resolve()
    except OSError:
        return None
    if root != target and root not in target.parents:
        return None
    return target


def main():
    try:
        envelope = json.load(sys.stdin)
    except Exception as e:
        fail(f"could not read arguments: {e}")

    arguments = envelope.get("arguments") or {}
    root = pathlib.Path(envelope.get("cwd") or ".").resolve()

    path = arguments.get("path")
    if not path:
        fail("'path' is required")
    target = resolve(root, path)
    if target is None:
        fail(f"refused: '{path}' is outside the project folder")
    if not target.is_file():
        fail(f"file not found: {path}")

    languages = arguments.get("languages") or ["en"]
    detail = bool(arguments.get("detail", False))

    try:
        import easyocr
    except ImportError:
        fail("the 'easyocr' package is required; declare it in tool.json "
             "dependencies and run '--mav tools sync'")

    # easyocr writes progress to stdout; point stdout at stderr during the noisy
    # calls so it cannot corrupt the one JSON object stdout owes Mavambo.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        reader = easyocr.Reader(languages, gpu=False, verbose=False)
        results = reader.readtext(str(target), detail=1)
    except Exception as e:
        sys.stdout = real_stdout
        fail(f"OCR failed: {e}")
    finally:
        sys.stdout = real_stdout

    text = "\n".join(str(r[1]) for r in results)
    if detail:
        result = {
            "text": text,
            "boxes": [
                {"text": str(r[1]),
                 "confidence": round(float(r[2]), 4),
                 "bbox": [[int(x), int(y)] for (x, y) in r[0]]}
                for r in results
            ],
        }
    else:
        result = text

    json.dump({"result": result}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
