# Mizan's themes

Theme packs every workspace can use (ADR-010 D3): one folder per theme with `theme.json`.
Activities add their own in `activities/<activity>/themes/`; developers ship signed theme packages.

## Composition: themes reference shared registries

A theme is a small manifest that composes shared building blocks by reference; it does not
duplicate font files or copy palette JSON:

```
themes/
  _fonts/                    one canonical copy per font family
    tajawal/
      font.json              family, files (weight/style), scripts, OFL license + source URLs
      tajawal-400.ttf
      tajawal-700.ttf
      OFL.txt
    …
  _palettes/                 named color token sets (original Mizan combinations of
    amber.json               Open Color (MIT) shades), each with source + license
    …
  amber/
    theme.json               the composition (see below)
```

```json
{
  "id": "mizan",
  "name": "ميزان",
  "name_en": "Mizan",
  "version": "1.0.0",
  "kind": "theme",
  "description": "…",
  "palette": "mizan",
  "fonts": {
    "body": "Manrope",
    "display": "Cormorant Garamond",
    "body_arabic": "Tajawal",
    "display_arabic": "Almarai",
    "files": [{"ref": "manrope"}, {"ref": "cormorant-garamond"}, {"ref": "tajawal"}, {"ref": "almarai"}]
  },
  "radius": "0.75rem",
  "shadows": "soft",
  "motion": "full"
}
```

- `palette` references `_palettes/<id>.json`; the loader expands it into the theme's `colors`.
- `fonts.files` entries are `{"ref": "<family id>"}`; the loader expands each into the family's
  plain file entries with canonical URLs `/themes/assets/fonts/<family>/<file>`.
- Family names in `fonts.body/display/body_arabic/display_arabic` are unchanged; renderers, the
  SDK and activation snapshots see the same effective theme as before the registries existed.
- Old per-pack URLs (`/themes/assets/files/<pack>/assets/<file>`) keep serving the registry's
  canonical bytes, so published site snapshots never break.
- Adding a font or palette means adding it to the registry once; any theme can then reference it.

Theme packages (developer-signed) stay self-contained: they embed their own colors and font
files and cannot reference the registries.

`app.platform.themes.service.check_file_themes()` validates the whole directory: registry
licenses and files, ref resolution, and each theme's expanded form against
`app.framework.manifest.theme_problems`.
