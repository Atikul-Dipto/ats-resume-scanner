# Bundled resume fonts

Embedded by `export_pdf.py`. The frontend loads the same faces as WOFF2
(`frontend/src/builder/fonts/`), so the preview breaks lines like the PDF.

| Files | Font | Source | License |
|---|---|---|---|
| `lmroman10-*.otf`, `lmsans10-*.otf` | Latin Modern 2.004 (the LaTeX / Computer Modern look) | [GUST e-foundry](https://www.gust.org.pl/projects/e-foundry/latin-modern), unmodified | GUST Font License (`GUST-FONT-LICENSE.txt`) |
| `SourceSans3-*.ttf` | Source Sans 3, 3.052R | [adobe-fonts/source-sans](https://github.com/adobe-fonts/source-sans/releases) | SIL OFL 1.1 (`OFL-SourceSans3.md`) |

Source Sans 3 is subset with fontTools to Latin, Latin Extended, Greek,
Cyrillic and common punctuation/symbols, with hinting removed (PDF viewers
don't use it). The WOFF2 copies are straight conversions of these files.
Characters outside a font fall back to DejaVu Sans when it is installed
(the Docker image installs it).
