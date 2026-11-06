# Caption fonts

The .ass captions use one font per language. Both fonts are bundled from Google Fonts (Noto family) and are
licensed under the SIL Open Font License 1.1 (OFL). Keep the OFL license text next to the font files when you add them.

| Language (`lang`) | File to place in this folder | Family name in the .ass style |
|---|---|---|
| `hi` (Hindi), `mr` (Marathi) | `NotoSansDevanagari-Bold.ttf` | Noto Sans Devanagari |
| `en` (English) | `NotoSans-Bold.ttf` | Noto Sans |

- Source: https://fonts.google.com/noto (Noto Sans Devanagari and Noto Sans, Bold weight).
- The font files are not in the repo yet. The code never downloads them.
- `h3/gate_d_audio.py` `ensure_font(fonts_dir=None, lang="hi")` checks the file for that language and raises a
  FileNotFoundError that names the missing file. `write_captions(..., lang=...)` runs this check before it writes.
- Captions are rendered by libass (HarfBuzz shaping) at assembly time with `fontsdir=assets/fonts`.
  The 6-word card limit, margins (160 / 160 / 896: bottom 35% = Instagram Reels and YouTube Shorts safe zone, owner 2026-11-07) and the rule that nothing sits above y=360 are the same for all languages.
