#!/usr/bin/env python3
"""Check that English captions and workbook labels preserve measurement evidence."""

from math import isclose
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "measurements/2026-11-03"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DISPLAY_TEXT = {
    "н/д": "n/a",
    "Флаг FPGA; ": "FPGA flag; ",
    "Неоднозначная фаза": "Ambiguous phase",
    "Вне калибровки": "Outside calibration",
}


def normalized_formula(text):
    for source, target in DISPLAY_TEXT.items():
        text = text.replace(source, target)
    # The original status formulas contain redundant backslashes before quotes.
    return text.replace("\\'", "'")


def main():
    count = 0
    image_tag = "{http://www.w3.org/2000/svg}image"
    for source in sorted((SERIES / "Осциллограммы").glob("point-*.svg")):
        if source.name.endswith(".en.svg"):
            continue
        target = source.with_name(source.stem + ".en.svg")
        a, b = ET.parse(source), ET.parse(target)
        assert [x.attrib for x in a.iter(image_tag)] == [x.attrib for x in b.iter(image_tag)], source
        count += 1
    assert count == 20, count
    numeric = formulas = 0
    with ZipFile(SERIES / "Стендовые измерения.xlsx") as source, ZipFile(SERIES / "Стендовые измерения.en.xlsx") as target:
        for path in ("xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
            a, b = ET.fromstring(source.read(path)), ET.fromstring(target.read(path))
            old = {x.get("r"): x for x in a.findall(".//m:c", NS)}
            new = {x.get("r"): x for x in b.findall(".//m:c", NS)}
            for address, cell in old.items():
                translated = new[address]
                assert cell.get("s") == translated.get("s"), (path, address, "style")
                f, g = cell.find("m:f", NS), translated.find("m:f", NS)
                assert (f is None) == (g is None), (path, address, "formula presence")
                if f is not None:
                    assert normalized_formula(f.text) == g.text, (path, address, "formula")
                    formulas += 1
                v, w = cell.find("m:v", NS), translated.find("m:v", NS)
                if cell.get("t", "n") == "n" and v is not None:
                    assert w is not None and isclose(float(v.text), float(w.text), rel_tol=1e-14, abs_tol=1e-12), (path, address, "number")
                    numeric += 1
            for name in ("cols", "mergeCells", "sheetViews", "autoFilter"):
                x, y = a.find("m:" + name, NS), b.find("m:" + name, NS)
                assert (x is None and y is None) or (x is not None and y is not None and ET.tostring(x) == ET.tostring(y)), (path, name)
        chart_path = "xl/drawings/charts/chart1.xml"
        ns = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
        a, b = ET.fromstring(source.read(chart_path)), ET.fromstring(target.read(chart_path))
        assert [x.text for x in a.findall(".//c:f", ns)] == [x.text for x in b.findall(".//c:f", ns)], "chart bindings"
        assert len(a.findall(".//c:ser", ns)) == len(b.findall(".//c:ser", ns)) == 2
    print(f"Verified {count} embedded images, {numeric} numeric cells, {formulas} formula expressions, layout and chart bindings.")


if __name__ == "__main__":
    main()
