# Translation and bilingual publication

[Русский](TRANSLATION.md) · **English**

Russian is the source language. Publish the Russian version first, then add or update English. Translation wording does not require separate approval by the author. Facts, measurements and limitations must agree in both versions.

## Structure

- `README.md` and other source `.md` files contain Russian; a full translation lives alongside each as `README.en.md` or `name.en.md`.
- Documents begin with “Русский / English” links. English documents link to English materials wherever they exist.
- Oscilloscope captions live in SVG files. Each `*.en.svg` contains an English caption and the same embedded PNG, without changing the measured signal.
- `Стендовые измерения.en.xlsx` contains English workbook, formula-output and chart labels. Numerical inputs, coefficients and calculation logic are preserved. Sheet names `Измерения` (Measurements) and `Расчёт` (Calculation) remain unchanged as formula-reference identifiers.
- `site-links.json` and `site-links.en.json` are the two language-specific link catalogues.
- PDF schematics and the BOM already use English technical labels; photographs, raw data, programs and original licences are shared between languages.

## Next publication

1. Edit the Russian document or add a new one. Create a new folder for each measurement series, preserving historical data.
2. Publish the Russian material. Until English is available, do not present Russian text under an English heading as a completed translation; indicate that translation is pending.
3. Translate the complete material, captions and explanations. Preserve commands, protocol fields, filenames, units, signs, numerical values, source links and qualifications about limitations.
4. Check links, tables, figures and calculations. A caption edit must not change a signal, photograph or original measurement bytes.
5. After review, run `python tools/i18n.py record SOURCE TARGET` for the reviewed pair and update the entry in `i18n/manifest.json`: `source`, `target`, both SHA-256 hashes and `status: current`. Add a new pair for new material. A changed source checksum identifies an outdated translation; do not update it without reviewing the translation.
6. Run `python tools/i18n.py status` and `python tools/i18n.py check --strict`. Run `python tools/check_localized_assets.py` after changing measurement translations. The captions can be regenerated with `python tools/localize_oscilloscope_captions.py`; review the result before recording its hashes. Update `AI_HANDOFF.md` and `PROJECT_LOG.md`, then their English versions. Publication to GitHub or the website follows the owner's instructions.

## Translation and evidence

`i18n/manifest.json` tracks translations; it is not a new hardware qualification. The root `manifest.json` and measurement manifest record the earlier package and remain historical. Adding language navigation to Markdown may differ from their old hashes. Primary data, original PNGs, firmware and earlier verification results are not rewritten. The translation manifest's `shared` section records separate SHA-256 hashes for checking unchanged common materials.

Russian source filenames, directory names and worksheet names remain valid identifiers. They do not mean the explanatory text is untranslated. The desktop application still uses a Russian interface: this publication localises project documentation and materials without changing application behaviour.
