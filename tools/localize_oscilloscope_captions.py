#!/usr/bin/env python3
"""Generate English caption layers without modifying embedded oscilloscope PNGs."""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "measurements/2026-11-03/Осциллограммы"
CAPTIONS = {
    "Расстояние по рулетке:": "Distance-meter reading:",
    "Точка": "Point",
    "опорный": "reference",
    "отражённый": "reflected",
    "ВЧ, ПЧ DDS": "HF, DDS IF",
    "НЧ, ПЧ DDS": "LF, DDS IF",
    " мм": " mm",
    " Гц": " Hz",
}


def translate_text(match):
    text = match.group(0)
    for source, target in CAPTIONS.items():
        text = text.replace(source, target)
    return re.sub(r"(?<=\d),(?=\d)", ".", text)


def main():
    for source in sorted(FOLDER.glob("point-*.svg")):
        if source.name.endswith(".en.svg"):
            continue
        original = source.read_text(encoding="utf-8")
        translated = re.sub(r"<text\b[^>]*>.*?</text>", translate_text, original, flags=re.S)
        image_tag = "{http://www.w3.org/2000/svg}image"
        before = [x.attrib for x in ET.fromstring(original).iter(image_tag)]
        after = [x.attrib for x in ET.fromstring(translated).iter(image_tag)]
        assert before == after, source
        if re.search(r"[А-Яа-яЁё]", " ".join(ET.fromstring(translated).itertext())):
            raise ValueError(f"Untranslated caption: {source}")
        target = source.with_name(source.stem + ".en.svg")
        target.write_text(translated, encoding="utf-8")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
