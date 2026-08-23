#!/usr/bin/env python3
"""OCR tool handler.

Contract:
  - Reads a single JSON object of arguments from stdin (falls back to argv[1]).
  - Arguments validate against the "parameters" schema in tool.json.
  - On success prints ONE JSON object to stdout and exits 0:
        {"ok": true, "text": "...", "boxes": [...]}   # boxes only if detail=true
  - On failure prints {"ok": false, "error": "..."} to stdout and exits 1.

Only stdout carries the JSON result. The OCR engine's own progress chatter is
forced to stderr so it never corrupts the JSON on stdout.
"""

import sys
import os
import json


def read_args():
    """Load the arguments object from stdin, or argv[1] as a fallback."""
    raw = ""
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
    if not raw.strip() and len(sys.argv) > 1:
        raw = sys.argv[1]
    if not raw.strip():
        return {}
    args = json.loads(raw)
    if not isinstance(args, dict):
        raise ValueError("arguments must be a JSON object")
    return args


def main():
    try:
        args = read_args()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"invalid arguments: {e}"}))
        return 1

    path = args.get("path")
    if not path:
        print(json.dumps({"ok": False, "error": "'path' is required"}))
        return 1
    if not os.path.isfile(path):
        print(json.dumps({"ok": False, "error": f"file not found: {path}"}))
        return 1

    languages = args.get("languages") or ["en"]
    detail = bool(args.get("detail", False))

    try:
        import easyocr
    except ImportError:
        print(json.dumps({
            "ok": False,
            "error": "the 'easyocr' package is required (pip install easyocr)",
        }))
        return 1

    try:
        # easyocr prints model-download/progress lines; keep stdout clean by
        # temporarily pointing stdout at stderr during the noisy calls.
        real_stdout = sys.stdout
        sys.stdout = sys.stderr
        try:
            reader = easyocr.Reader(languages, gpu=False, verbose=False)
            results = reader.readtext(path, detail=1)
        finally:
            sys.stdout = real_stdout

        lines = [str(r[1]) for r in results]
        out = {"ok": True, "text": "\n".join(lines)}

        if detail:
            out["boxes"] = [
                {
                    "text": str(r[1]),
                    "confidence": round(float(r[2]), 4),
                    "bbox": [[int(x), int(y)] for (x, y) in r[0]],
                }
                for r in results
            ]

        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
