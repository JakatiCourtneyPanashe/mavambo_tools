"""Extract text from PDF files, for Mavambo.

Reads one JSON envelope on stdin and writes one JSON object on stdout. Nothing
here knows about Mavambo beyond that contract; it is an ordinary script that
happens to be launched by an agent.

Three things this tool does that are not obvious, and each of them is a rule
the runtime cannot enforce on a tool's behalf:

  It takes a list of paths, not one.
      An installed tool is approval-gated, and an approval-gated call cannot
      ride in a parallel batch -- so the agent reaches this tool one call at a
      time, with a human prompt each time. A per-file tool would mean one
      prompt per file. Measured on a different tool, taking a list instead cut
      the same job from eleven model calls to five.

  It refuses a path that leaves the project.
      The runtime pins the working directory to the active project, which
      decides where relative paths start -- it does not stop `../../` from
      walking out. A tool that reads files has to check that itself.

  It bounds its own output.
      The runtime truncates anything oversized, but truncation is a blunt
      instrument: it would cut mid-sentence and spend the whole budget on file
      one of four. Choosing what to drop, and saying so, is the tool's job.
"""

import json
import pathlib
import sys

# What one call may return in total, and per file.
#
# Comfortably inside the runtime's own 10,000-character result bound, because
# being truncated by the caller is strictly worse than paginating: the caller
# cuts at a byte offset, mid-word, with no idea which file it was in the
# middle of. A page of dense prose is roughly 2,500 characters, so this is a
# few pages of real reading per call and the rest is fetched by asking again
# with a different range.
MAX_TOTAL_CHARS = 8_000
MAX_CHARS_PER_FILE = 4_000

# How many pages to read when no range is given.
#
# Small on purpose. The page count comes back on every call whether or not the
# text does, so the agent always learns how much there is and can ask for the
# rest by range. Guessing large would spend the budget before anyone had
# decided the document was the right one.
DEFAULT_PAGES = 3


def fail(message):
    json.dump({"error": message}, sys.stdout)
    raise SystemExit(0)


def resolve(root, name):
    """A path inside the project, or None.

    Two gates, because either alone has a hole. Rejecting `..` and absolute
    spellings catches the obvious attempt; resolving and comparing catches
    what a symlink would otherwise do.
    """
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


def read_pdf(reader, first, last, budget):
    """Text for one page range, bounded. Returns (text, pages_read, truncated)."""
    collected, used, pages_read = [], 0, 0
    for number in range(first, last + 1):
        try:
            text = (reader.pages[number - 1].extract_text() or "").strip()
        except Exception as error:                      # noqa: BLE001
            # One unreadable page must not lose the pages around it. A PDF
            # with a damaged object is common and usually still worth reading.
            text = f"[page {number} could not be read: {error}]"
        pages_read += 1
        if not text:
            # Almost always a scanned page: an image with no text layer.
            # Saying so is worth more than an empty section, because it tells
            # the reader the file needs OCR rather than a different range.
            text = "[no extractable text -- this page is probably a scan]"
        block = f"--- page {number} ---\n{text}"
        if used + len(block) > budget:
            return "\n\n".join(collected), pages_read - 1, True
        collected.append(block)
        used += len(block) + 2
    return "\n\n".join(collected), pages_read, False


def main():
    payload = json.load(sys.stdin)
    arguments = payload.get("arguments") or {}
    root = pathlib.Path(payload["cwd"]).resolve()

    try:
        from pypdf import PdfReader
    except ImportError:
        # Reachable only if the environment drifted after install: Mavambo
        # refuses to load a tool whose declared dependencies are absent. Worth
        # answering anyway, because "run tools sync" is actionable and an
        # ImportError traceback is not.
        fail("pypdf is not installed. Run: --mav tools sync")

    paths = arguments.get("paths") or []
    first = arguments.get("first_page")
    last = arguments.get("last_page")
    if first and last and last < first:
        fail(f"last_page ({last}) is before first_page ({first})")

    sections, remaining = [], MAX_TOTAL_CHARS
    for name in paths:
        target = resolve(root, name)
        if target is None:
            sections.append(f"{name}: refused -- outside the project folder")
            continue
        if not target.is_file():
            sections.append(f"{name}: no such file")
            continue

        try:
            reader = PdfReader(str(target))
            if getattr(reader, "is_encrypted", False):
                # An empty-password decrypt covers the common "protected but
                # not really" case. A real password is not something this tool
                # can be given: it would have to arrive as an argument, and
                # arguments are recorded in the session file and replayed to
                # the model on every later call.
                try:
                    reader.decrypt("")
                except Exception:                        # noqa: BLE001
                    sections.append(f"{name}: encrypted, and no password was supplied")
                    continue
            total = len(reader.pages)
        except Exception as error:                       # noqa: BLE001
            sections.append(f"{name}: not a readable PDF ({error})")
            continue

        if total == 0:
            sections.append(f"{name}: 0 pages")
            continue

        start = min(max(first or 1, 1), total)
        end = min(last or (start + DEFAULT_PAGES - 1), total)
        budget = min(MAX_CHARS_PER_FILE, max(remaining, 0))
        if budget <= 0:
            sections.append(
                f"{name}: {total} pages -- not read, this call's budget is spent. "
                "Ask for this file on its own."
            )
            continue

        text, pages_read, truncated = read_pdf(reader, start, end, budget)
        remaining -= len(text)
        header = f"{name}: {total} pages, showing {start}-{start + pages_read - 1}"
        if truncated or end < total:
            header += f" (ask for first_page {start + pages_read} for more)"
        sections.append(f"{header}\n{text}")

    json.dump({"result": "\n\n".join(sections) or "no files given"}, sys.stdout)


if __name__ == "__main__":
    main()
