"""Loaders that produce KnowledgeItem batches from canonical sources.

  * ``load_csi()`` — config/csi_master_format.json
  * ``load_ibc()`` — config/ibc_use_groups.json (marked permit_only=True)
  * ``load_reference_aacounty()`` — Anne Arundel CD-set extraction

Each loader returns a list of ``KnowledgeItem`` — the caller pushes the lot
into the store.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .schema import KnowledgeItem, KnowledgeKind, KnowledgeLayer

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config"
REFERENCE = REPO_ROOT / "reference_examples"


# ---------------------------------------------------------------------------
# CSI MasterFormat
# ---------------------------------------------------------------------------

def load_csi(path: Optional[Path] = None) -> list[KnowledgeItem]:
    path = path or (CONFIG / "csi_master_format.json")
    data = json.loads(path.read_text())
    items: list[KnowledgeItem] = []
    for div in data.get("divisions", []):
        code = div["code"]
        items.append(KnowledgeItem(
            id=f"csi:{code}",
            kind=KnowledgeKind.CSI_DIVISION,
            layer=KnowledgeLayer.CSI,
            name=div["name"],
            description=div.get("notes", ""),
            code=code,
            csi_division=code,
            sheets=list(div.get("sheets", [])),
            payload={"notes": div.get("notes", "")},
        ))
    logger.info("CSI: %d divisions loaded.", len(items))
    return items


# ---------------------------------------------------------------------------
# IBC use groups + egress
# ---------------------------------------------------------------------------

def load_ibc(path: Optional[Path] = None) -> list[KnowledgeItem]:
    path = path or (CONFIG / "ibc_use_groups.json")
    data = json.loads(path.read_text())
    items: list[KnowledgeItem] = []

    for grp in data.get("use_groups", []):
        code = grp["code"]
        ex = ", ".join(grp.get("examples", [])[:4])
        desc = f"{grp['name']} — examples: {ex}" if ex else grp["name"]
        items.append(KnowledgeItem(
            id=f"ibc:use:{code}",
            kind=KnowledgeKind.IBC_USE_GROUP,
            layer=KnowledgeLayer.IBC,
            name=f"Use Group {code}: {grp['name']}",
            description=desc,
            code=code,
            aliases=grp.get("examples", []),
            permit_only=True,
            payload=grp,
        ))

    for assy in data.get("fire_rating_assemblies", []):
        code = assy["code"]
        items.append(KnowledgeItem(
            id=f"ibc:fr:{code}",
            kind=KnowledgeKind.IBC_FIRE_RATING,
            layer=KnowledgeLayer.IBC,
            name=f"{code} — {assy['name']}",
            description=f"{assy.get('typical', '')}. Used at: " +
                        ", ".join(assy.get("examples", [])),
            code=code,
            permit_only=True,
            payload=assy,
        ))

    egress = data.get("egress_minimums") or {}
    if egress:
        items.append(KnowledgeItem(
            id="ibc:egress:minimums",
            kind=KnowledgeKind.IBC_EGRESS_RULE,
            layer=KnowledgeLayer.IBC,
            name="IBC Egress Minimums",
            description="Standard IBC egress minimum dimensions and thresholds.",
            code="EGRESS",
            permit_only=True,
            payload=egress,
        ))

    logger.info("IBC: %d items loaded (use groups + fire ratings + egress).", len(items))
    return items


# ---------------------------------------------------------------------------
# Reference CD set — Anne Arundel
# ---------------------------------------------------------------------------

def load_reference_aacounty(
    extraction_path: Optional[Path] = None,
) -> list[KnowledgeItem]:
    """Load the pre-extracted Anne Arundel CD set patterns.

    Requires ``reference_examples/aacounty_extracted.json`` (produced by the
    extraction step). If missing, returns an empty list with a warning.
    """
    extraction_path = extraction_path or (REFERENCE / "aacounty_extracted.json")
    if not extraction_path.exists():
        logger.warning("Reference extraction missing at %s. Skipping.", extraction_path)
        return []
    data = json.loads(extraction_path.read_text())
    items: list[KnowledgeItem] = []

    # Abbreviations
    for code, name in (data.get("abbreviations") or {}).items():
        items.append(KnowledgeItem(
            id=f"ref:aa:abbr:{code}",
            kind=KnowledgeKind.ABBREVIATION,
            layer=KnowledgeLayer.REFERENCE,
            name=name,
            description=f"Abbreviation '{code}' for '{name}'.",
            code=code,
            aliases=[code],
        ))

    # Sheet templates — every captured (code, name) pair becomes a template.
    for code, sheet_name in (data.get("sheets") or {}).items():
        items.append(KnowledgeItem(
            id=f"ref:aa:sheet:{code}",
            kind=KnowledgeKind.SHEET_TEMPLATE,
            layer=KnowledgeLayer.REFERENCE,
            name=f"{code} — {sheet_name}",
            description=f"Anne Arundel reference sheet {code}: {sheet_name}.",
            code=code,
            sheets=[code],
            payload={"source": "aacounty_30_sd"},
        ))

    logger.info("Reference (Anne Arundel): %d items loaded.", len(items))
    return items


# ---------------------------------------------------------------------------
# Drafting standards (AIA / NCS / ISO 128) — config/drafting/*.json
# ---------------------------------------------------------------------------

def load_drafting(drafting_dir: Optional[Path] = None) -> list[KnowledgeItem]:
    """Index AIA layers, line types, scales, sheet types into the knowledge DB."""
    drafting_dir = drafting_dir or (CONFIG / "drafting")
    if not drafting_dir.exists():
        logger.warning("Drafting dir missing at %s. Skipping.", drafting_dir)
        return []

    items: list[KnowledgeItem] = []

    # 1) AIA layers
    layers_path = drafting_dir / "aia_layers.json"
    if layers_path.exists():
        data = json.loads(layers_path.read_text())
        for disc_code, disc_name in (data.get("disciplines") or {}).items():
            items.append(KnowledgeItem(
                id=f"draft:disc:{disc_code}",
                kind=KnowledgeKind.DISCIPLINE_CODE,
                layer=KnowledgeLayer.DRAFTING,
                name=f"{disc_code} — {disc_name}",
                description=f"AIA/NCS discipline letter: {disc_code} = {disc_name}",
                code=disc_code,
            ))
        for stat_code, stat_name in (data.get("status_codes") or {}).items():
            items.append(KnowledgeItem(
                id=f"draft:stat:{stat_code}",
                kind=KnowledgeKind.STATUS_CODE,
                layer=KnowledgeLayer.DRAFTING,
                name=f"{stat_code} — {stat_name}",
                description=f"AIA/NCS status code: {stat_code} = {stat_name}",
                code=stat_code,
            ))
        for layer in data.get("layers", []):
            items.append(KnowledgeItem(
                id=f"draft:layer:{layer['name']}",
                kind=KnowledgeKind.AIA_LAYER,
                layer=KnowledgeLayer.DRAFTING,
                name=layer["name"],
                description=(
                    f"{layer['desc']} "
                    f"(linetype: {layer['linetype']}, weight: {layer['lineweight_mm']} mm, "
                    f"color ACI: {layer['color']})"
                ),
                code=layer["name"],
                csi_division=_csi_for_layer_name(layer["name"]),
                payload=layer,
            ))

    # 2) Line types + weights
    lt_path = drafting_dir / "line_types.json"
    if lt_path.exists():
        data = json.loads(lt_path.read_text())
        for lt in data.get("line_types", []):
            items.append(KnowledgeItem(
                id=f"draft:linetype:{lt['name']}",
                kind=KnowledgeKind.LINE_TYPE,
                layer=KnowledgeLayer.DRAFTING,
                name=lt["name"],
                description=f"{lt['meaning']} (visual: {lt.get('viz', '')})",
                code=lt["name"],
                payload=lt,
            ))
        for lw in data.get("lineweights_mm", []):
            items.append(KnowledgeItem(
                id=f"draft:lineweight:{lw['weight']}",
                kind=KnowledgeKind.LINE_WEIGHT,
                layer=KnowledgeLayer.DRAFTING,
                name=f"{lw['weight']} mm",
                description=f"Line weight {lw['weight']} mm — {lw['use']}",
                code=str(lw["weight"]),
                payload=lw,
            ))

    # 3) Scales
    sc_path = drafting_dir / "scales.json"
    if sc_path.exists():
        data = json.loads(sc_path.read_text())
        for s in data.get("architectural_imperial", []):
            items.append(KnowledgeItem(
                id=f"draft:scale:arch:{s['ratio']}",
                kind=KnowledgeKind.ARCH_SCALE,
                layer=KnowledgeLayer.DRAFTING,
                name=s["verbal"],
                description=(
                    f"Architectural scale {s['verbal']} ({s['ratio']}); "
                    f"{s['real_in_per_paper_in']} real inches per paper inch."
                    + (f" Typical: {s.get('typical_use')}." if s.get("typical_use") else "")
                ),
                code=s["ratio"],
                payload=s,
            ))
        for s in data.get("engineering_imperial", []):
            items.append(KnowledgeItem(
                id=f"draft:scale:eng:{s['ratio']}",
                kind=KnowledgeKind.ARCH_SCALE,
                layer=KnowledgeLayer.DRAFTING,
                name=s["verbal"],
                description=(
                    f"Engineering scale {s['verbal']} ({s['ratio']}); "
                    f"{s['real_in_per_paper_in']} real inches per paper inch."
                ),
                code=s["ratio"],
                payload=s,
            ))

    # 4) Sheet-type digits
    st_path = drafting_dir / "sheet_types.json"
    if st_path.exists():
        data = json.loads(st_path.read_text())
        for st in data.get("sheet_type_digits", []):
            items.append(KnowledgeItem(
                id=f"draft:sheet_digit:{st['digit']}",
                kind=KnowledgeKind.SHEET_TYPE_DIGIT,
                layer=KnowledgeLayer.DRAFTING,
                name=f"Sheet type {st['digit']} — {st['name']}",
                description=(
                    f"NCS sheet-type digit {st['digit']} groups sheets of type "
                    f"'{st['name']}'. Examples: {', '.join(st.get('examples', [])[:3])}"
                ),
                code=st["digit"],
                payload=st,
            ))

    logger.info("Drafting: %d items loaded.", len(items))
    return items


# Mapping from layer-name prefix to plausible CSI division.
_LAYER_PREFIX_TO_CSI = {
    "A-WALL": "09", "A-WALL-EXST": "02", "A-WALL-DEMO": "02",
    "A-WALL-NEWW": "09", "A-WALL-FIRE": "07", "A-WALL-PATT": "09",
    "A-DOOR": "08", "A-GLAZ": "08",
    "A-COLS": "05",
    "A-FLOR-WDWK": "06", "A-FLOR-PFIX": "22", "A-FLOR-FIXT": "11",
    "A-EQPM": "11",
    "A-CLNG": "09",
    "A-ROOF": "07",
    "A-LITE": "26",
    "S-": "05",
}


def _csi_for_layer_name(layer_name: str) -> str:
    for prefix, div in _LAYER_PREFIX_TO_CSI.items():
        if layer_name.startswith(prefix):
            return div
    return ""


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def load_all() -> list[KnowledgeItem]:
    return [
        *load_csi(),
        *load_drafting(),
        *load_ibc(),
        *load_reference_aacounty(),
    ]
