# pdf — a Mavambo tool

Reads text out of PDF files in the active project folder.

## Install

```
python main.py --mav tools install <this repository's URL>
```

You will be asked twice, and the two questions are different.

The first is whether to install the tool. Answering yes copies files and runs
nothing. The prompt shows the command that will eventually run, the arguments
it takes, and its timeout.

The second is whether to install `pypdf`. That one downloads and **runs** code
from PyPI, into `tools/.venv` — an environment shared by installed tools and
separate from Mavambo's own. Declining leaves the tool installed and not
loaded; `--mav tools sync` finishes it later.

Then start a new session. The tool list is fixed when a session starts, so a
tool installed mid-session takes effect in the next one.

## Use

```
pdf(paths, first_page?, last_page?, reason)
```

Paths are relative to the active project folder. Anything outside it is
refused.

```
read the first two pages of docs/spec.pdf
summarise report.pdf and appendix.pdf
```

Every call asks for approval, showing the arguments, because an installed tool
is code Mavambo did not write.

## What it returns

Page count for every file, always — so you can ask for a different range
without guessing — and the extracted text for the pages requested. Without a
range it reads the first three pages.

Output is bounded to roughly 8,000 characters per call, 4,000 per file. When
that runs out it says which page to resume from. This is not a limitation of
PDFs; it is that a tool result is replayed on every later call in the turn, so
a large one is charged repeatedly.

A page with no text layer is reported as such rather than returned empty —
that means a scan, and it needs OCR, which this tool does not do.

## Notes

- Encrypted PDFs are attempted with an empty password, which covers the
  "protected but not really" case. A real password would have to be passed as
  an argument, and arguments are written to the session file and replayed to
  the model, so this tool does not accept one.
- It takes a **list** of paths on purpose. An approval-gated tool is reached
  one call at a time, so a per-file tool would mean one approval per file.
- No network access. It declares no `network` capability and reads no
  environment variables.
