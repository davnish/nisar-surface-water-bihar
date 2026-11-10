"""Build the QGIS project from the layer manifest written by `nisar-water qgis`.

Runs under QGIS's own Python (PyQGIS), not the project's uv environment:
    QT_QPA_PLATFORM=offscreen /Applications/QGIS.app/Contents/MacOS/python3.12 \
        tools/build_qgis_project.py data/processed/qgis/manifest.json qgis/nisar_water.qgz
(`nisar-water qgis` does this for you.)

Layers are grouped and styled; every dated layer gets a fixed temporal range [date, date + 12 days), so the
QGIS Temporal Controller (View > Panels > Temporal Controller) steps through acquisitions. Paths are
saved relative to the project file.
"""
import json
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsColorRampShader, QgsContrastEnhancement, QgsCoordinateReferenceSystem,
                       QgsDateTimeRange, QgsFillSymbol, QgsMultiBandColorRenderer, QgsPalettedRasterRenderer,
                       QgsProject, QgsRasterLayer, QgsRasterShader, QgsRectangle, QgsReferencedRectangle,
                       QgsSingleBandGrayRenderer, QgsSingleBandPseudoColorRenderer, QgsVectorLayer)
from qgis.PyQt.QtCore import QDate, QDateTime, QTime
from qgis.PyQt.QtGui import QColor

REPEAT_DAYS = 12
# top of the layer tree draws on top
GROUP_ORDER = ["AOI", "Water", "Change", "New water", "Reference (R00)", "NISAR", "Sentinel-2", "Basemaps"]
# groups switched on when the project opens
VISIBLE_GROUPS = ("AOI", "Water — C3 champion: LightGBM, scene-relative features (L07)", "Reference (R00)",
                  "NISAR L-band asc 98/14 — HH γ0 dB (Lee 7×7)", "Basemaps")
BASEMAPS = [
    ("Esri World Imagery", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 19),
    ("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19),
]


def paletted(layer, classes, opacity=1.0):
    """classes: [(value, '#hex', label)]; values not listed (e.g. 0 non-water) render transparent."""
    items = [QgsPalettedRasterRenderer.Class(v, QColor(c), lab) for v, c, lab in classes]
    r = QgsPalettedRasterRenderer(layer.dataProvider(), 1, items)
    r.setOpacity(opacity)
    layer.setRenderer(r)


def gray(layer, lo, hi):
    r = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
    ce = QgsContrastEnhancement(layer.dataProvider().dataType(1))
    ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    ce.setMinimumValue(lo)
    ce.setMaximumValue(hi)
    r.setContrastEnhancement(ce)
    layer.setRenderer(r)


def ramp(layer, stops, opacity=1.0):
    """stops: [(value, '#hex', label)] interpolated."""
    shader_fn = QgsColorRampShader()
    shader_fn.setColorRampType(QgsColorRampShader.Interpolated)
    shader_fn.setColorRampItemList([QgsColorRampShader.ColorRampItem(v, QColor(c), lab) for v, c, lab in stops])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(shader_fn)
    r = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    r.setOpacity(opacity)
    layer.setRenderer(r)


def style(layer, kind):
    if kind == "db_hh":
        gray(layer, -25.0, -2.0)
    elif kind == "db_hv":
        gray(layer, -30.0, -10.0)
    elif kind == "water":
        paletted(layer, [(1, "#2a78d6", "Water")])
    elif kind == "s2_water":
        paletted(layer, [(1, "#1baf7a", "S2 water")], 0.8)
    elif kind == "s1_water":
        paletted(layer, [(1, "#e87ba4", "S1 water")], 0.8)
    elif kind == "persistent":
        paletted(layer, [(1, "#0d366b", "Persistent water")], 0.9)
    elif kind == "occurrence":
        ramp(layer, [(1, "#cde2fb", "1 %"), (50, "#3987e5", "50 %"), (100, "#0d366b", "100 %")], 0.9)
    elif kind == "change":
        paletted(layer, [(0, "#d9d6cc", "Stable non-water"), (1, "#2a78d6", "Stable water"),
                         (2, "#1baf7a", "Newly detected water (gain)"), (3, "#eb6834", "Water loss (receded)")], 0.9)
    elif kind == "new_water":
        paletted(layer, [(1, "#2a78d6", "Persistent water"), (2, "#eda100", "New water outside persistent")], 0.9)
    elif kind == "split":
        paletted(layer, [(1, "#2a78d6", "Train"), (2, "#eb6834", "Test")], 0.35)
    elif kind == "rgb":
        r = QgsMultiBandColorRenderer(layer.dataProvider(), 1, 2, 3)
        layer.setRenderer(r)
    elif kind == "bbox":
        layer.renderer().setSymbol(QgsFillSymbol.createSimple(
            {"color": "0,0,0,0", "outline_color": "#0b0b0b", "outline_width": "0.8"}))
    elif kind == "footprints":
        layer.renderer().setSymbol(QgsFillSymbol.createSimple(
            {"color": "0,0,0,0", "outline_color": "#eb6834", "outline_width": "0.4"}))


def set_temporal(layer, date: str):
    y, m, d = map(int, date.split("-"))
    start = QDateTime(QDate(y, m, d), QTime(0, 0))
    # closed range ending 1 s before the next acquisition (a half-open end does not survive project save)
    rng = QgsDateTimeRange(start, start.addDays(REPEAT_DAYS).addSecs(-1))
    tp = layer.temporalProperties()
    tp.setIsActive(True)
    try:
        from qgis.core import Qgis
        tp.setMode(Qgis.RasterTemporalMode.FixedTemporalRange)
    except AttributeError:  # older API
        from qgis.core import QgsRasterLayerTemporalProperties
        tp.setMode(QgsRasterLayerTemporalProperties.ModeFixedTemporalRange)
    tp.setFixedTemporalRange(rng)
    return rng


def group_rank(name: str) -> int:
    return next((i for i, g in enumerate(GROUP_ORDER) if name.startswith(g)), len(GROUP_ORDER))


def main(manifest_path: str, out_path: str):
    manifest = json.loads(Path(manifest_path).read_text())
    repo = Path(manifest_path).resolve().parents[3]  # data/processed/qgis/manifest.json -> repo root
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    project = QgsProject.instance()
    project.clear()
    crs = QgsCoordinateReferenceSystem(manifest["crs"])
    project.setCrs(crs)
    project.setTitle("NISAR L-band surface water — Bihar (InGARSS 2026 YP Hackathon)")
    root = project.layerTreeRoot()

    layers = sorted(manifest["layers"], key=lambda l: group_rank(l["group"]))
    layers += [{"group": "Basemaps", "name": n, "kind": "xyz", "url": u, "zmax": z} for n, u, z in BASEMAPS]

    groups, ranges, missing = {}, [], []
    for spec in layers:
        if spec["kind"] == "xyz":
            url = spec["url"].replace("{", "%7B").replace("}", "%7D")
            layer = QgsRasterLayer(f"type=xyz&url={url}&zmax={spec['zmax']}&zmin=0", spec["name"], "wms")
        else:
            path = repo / spec["path"]
            if not path.exists():
                missing.append(spec["path"])
                continue
            layer = (QgsVectorLayer(str(path), spec["name"], "ogr") if spec["kind"] == "vector"
                     else QgsRasterLayer(str(path), spec["name"]))
        if not layer.isValid():
            missing.append(spec.get("path", spec["name"]))
            continue
        style(layer, spec.get("style", ""))
        if spec.get("date"):
            ranges.append(set_temporal(layer, spec["date"]))
        if spec["group"] not in groups:
            g = root.addGroup(spec["group"])
            g.setItemVisibilityChecked(spec["group"] in VISIBLE_GROUPS)
            g.setExpanded(False)
            groups[spec["group"]] = g
        project.addMapLayer(layer, False)
        node = groups[spec["group"]].addLayer(layer)
        node.setItemVisibilityChecked(spec.get("visible", True) or bool(spec.get("date")))
        if spec["kind"] == "xyz" and spec["name"] != BASEMAPS[0][0]:
            node.setItemVisibilityChecked(False)

    # default view: the bbox grid
    a, _, c, _, e, f = manifest["extent_transform"][:6]
    rows, cols = manifest["shape"]
    project.viewSettings().setDefaultViewExtent(
        QgsReferencedRectangle(QgsRectangle(c, f + e * rows, c + a * cols, f), crs))
    if ranges:
        overall = QgsDateTimeRange(min(r.begin() for r in ranges), max(r.end() for r in ranges))
        project.timeSettings().setTemporalRange(overall)
        try:
            from qgis.core import QgsUnitTypes
            project.timeSettings().setTimeStepUnit(QgsUnitTypes.TemporalDays)
            project.timeSettings().setTimeStep(REPEAT_DAYS)
        except Exception:
            pass
    project.writeEntryBool("Paths", "/Absolute", False)
    project.setFileName(str(out))
    if not project.write():
        raise SystemExit(f"failed to write {out}")
    print(f"wrote {out}: {sum(len(g.children()) for g in groups.values())} layers in {len(groups)} groups")
    if missing:
        print(f"skipped {len(missing)} missing/invalid: {missing[:5]}")


if __name__ == "__main__":
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        main(sys.argv[1], sys.argv[2])
    finally:
        qgs.exitQgis()
