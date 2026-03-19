"""PlanSearch — Floor Area Extractor.

Extracts floor area from planning application proposal text.
The proposal is legally required to be accurate under the
Planning and Development Act 2000.

NPAD FloorArea is known to have data quality issues (e.g. 165,795,000 m²
for a 16,386 m² building). The proposal description is the source of truth.
"""

import re
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# ── Floor area extraction from proposal text ─────────────────────────────

# Patterns for square metres (most common in Irish planning)
_SQM_PATTERNS = [
    re.compile(r"(\d[\d,\.]*)\s*(?:sq\.?\s*m(?:etres?)?\.?|m²|m2|sqm)", re.IGNORECASE),
    re.compile(r"(\d[\d,\.]*)\s*(?:square\s*met(?:re|er)s?)", re.IGNORECASE),
    re.compile(
        r"(?:gross\s+floor\s+area|gfa|total\s+(?:floor\s+)?area)\s+(?:of\s+)?(\d[\d,\.]*)\s*(?:sq\.?\s*m|m²|sqm)",
        re.IGNORECASE,
    ),
    re.compile(r"totalling\s+(\d[\d,\.]*)\s*(?:sq\.?\s*m|m²|sqm)", re.IGNORECASE),
]

# Patterns for square feet (convert to m²)
_SQFT_PATTERNS = [
    re.compile(r"(\d[\d,\.]*)\s*(?:sq\.?\s*f(?:ee|oo)?t\.?|ft²|sqft)", re.IGNORECASE),
    re.compile(r"(\d[\d,\.]*)\s*(?:square\s*feet|square\s*foot)", re.IGNORECASE),
]

SQ_FT_TO_SQ_M = 0.0929

# Patterns for residential unit counts
_UNIT_PATTERNS = [
    # "45 residential units" | "120 apartments" | "200 dwelling units"
    re.compile(
        r"(\d[\d,]*)\s*(?:no\.?\s*)?(?:residential\s+units?|apartments?|dwelling\s+units?|dwellings?|houses?|units?\s+(?:of\s+)?accommodation)",
        re.IGNORECASE,
    ),
    # "comprising 45 units" | "containing 200 units"
    re.compile(
        r"(?:comprising|containing|of|totalling|total(?:ing)?)\s+(\d[\d,]*)\s*(?:no\.?\s*)?(?:units?|beds?)",
        re.IGNORECASE,
    ),
]


def _parse_number(s: str) -> float:
    """Parse a number string like '16,386' or '16386.5'."""
    return float(s.replace(",", ""))


def extract_floor_area_from_proposal(proposal: str) -> Optional[float]:
    """Extract floor area from planning application proposal text.

    The proposal is legally required to be accurate under
    Planning and Development Act 2000.

    Returns area in m².
    """
    if not proposal:
        return None

    areas: List[float] = []

    # Square metres
    for pattern in _SQM_PATTERNS:
        for match in pattern.finditer(proposal):
            try:
                val = _parse_number(match.group(1))
                if 10 <= val <= 500_000:
                    areas.append(val)
            except (ValueError, IndexError):
                pass

    # Square feet → convert
    for pattern in _SQFT_PATTERNS:
        for match in pattern.finditer(proposal):
            try:
                val = _parse_number(match.group(1)) * SQ_FT_TO_SQ_M
                if 10 <= val <= 500_000:
                    areas.append(val)
            except (ValueError, IndexError):
                pass

    if not areas:
        return None

    # The largest area mentioned is typically the total GFA
    return max(areas)


def extract_site_area_from_proposal(proposal: str) -> Optional[float]:
    """Extract site area in hectares from planning proposal text.

    Legally required to be accurate under Planning & Development Act 2000.
    Returns area in hectares.
    """
    if not proposal:
        return None

    areas_ha: List[float] = []

    # Hectare patterns — note: 'hectares' is h-e-c-t-a-r-e-s, NOT ha-ctares
    _HA_PATTERNS = [
        re.compile(r"c\.?\s*(\d[\d,\.]*)\s*(?:ha|hectares?)", re.IGNORECASE),
        re.compile(r"(\d[\d,\.]*)\s*(?:ha|hectares?)(?:\s+site)?", re.IGNORECASE),
        re.compile(r"site\s+(?:area\s+)?of\s+(\d[\d,\.]*)\s*(?:ha|hectares?)", re.IGNORECASE),
        re.compile(r"(\d[\d,\.]*)\s*(?:ha|hectares?)\s+site", re.IGNORECASE),
        re.compile(r"approx(?:imately|\.)\s+(\d[\d,\.]*)\s*(?:ha|hectares?)", re.IGNORECASE),
    ]

    # m² site patterns (convert to ha)
    _SQM_SITE_PATTERNS = [
        re.compile(r"site\s+(?:area\s+)?of\s+(\d[\d,\.]*)\s*(?:sq\.?\s*m|m²|sqm)", re.IGNORECASE),
        re.compile(r"(\d[\d,\.]*)\s*(?:sq\.?\s*m|m²|sqm)\s+site", re.IGNORECASE),
    ]

    # Acre patterns (convert to ha)
    _ACRE_PATTERNS = [
        re.compile(r"(\d[\d,\.]*)\s*acres?", re.IGNORECASE),
    ]

    for pattern in _HA_PATTERNS:
        for match in pattern.finditer(proposal):
            try:
                val = _parse_number(match.group(1))
                if 0.001 <= val <= 500:
                    areas_ha.append(val)
            except (ValueError, IndexError):
                pass

    for pattern in _SQM_SITE_PATTERNS:
        for match in pattern.finditer(proposal):
            try:
                val = _parse_number(match.group(1)) / 10_000
                if 0.001 <= val <= 500:
                    areas_ha.append(val)
            except (ValueError, IndexError):
                pass

    for pattern in _ACRE_PATTERNS:
        for match in pattern.finditer(proposal):
            try:
                val = _parse_number(match.group(1)) * 0.404686
                if 0.001 <= val <= 500:
                    areas_ha.append(val)
            except (ValueError, IndexError):
                pass

    # Return first match — site area is typically stated once
    return areas_ha[0] if areas_ha else None


def extract_unit_count_from_proposal(proposal: str) -> Optional[int]:
    """Extract residential unit count from proposal text."""
    if not proposal:
        return None

    for pattern in _UNIT_PATTERNS:
        for match in pattern.finditer(proposal):
            try:
                count = int(_parse_number(match.group(1)))
                if 1 <= count <= 10_000:
                    return count
            except (ValueError, IndexError):
                continue

    return None


# ── Reconciliation: description-first, NPAD fallback ─────────────────────


def get_reliable_floor_area(
    npad_floor_area: Optional[float],
    proposal: Optional[str],
) -> Optional[float]:
    """Get the most reliable floor area for value estimation.

    Priority:
    1. Proposal text extraction (legally accurate, required by Planning Act)
    2. NPAD FloorArea only if it passes sanity checks AND no description
       area found

    NPAD FloorArea is known to have data quality issues (e.g. 165,795,000 m²
    for a 16,386 m² building). The proposal description is legally mandated
    to be accurate under Planning and Development Act 2000.
    """
    # Always try to extract from description first
    description_area = extract_floor_area_from_proposal(proposal)

    if description_area:
        return description_area

    # Fall back to NPAD only with strict sanity checks
    # Cap at 100,000 m² — largest single building in Ireland is ~100k m²
    if npad_floor_area and 10 <= npad_floor_area <= 100_000:
        return npad_floor_area

    return None


def get_reliable_units(
    npad_units: Optional[int],
    proposal: Optional[str],
) -> Optional[int]:
    """Get the most reliable residential unit count.

    Priority: description extraction, then NPAD fallback with sanity check.
    """
    description_units = extract_unit_count_from_proposal(proposal)

    if description_units:
        return description_units

    # Fall back to NPAD with sanity check
    if npad_units and 1 <= npad_units <= 5_000:
        return npad_units

    return None


# ── Legacy aliases (used by npad_ingest.py) ───────────────────────────────

def reconcile_floor_area(
    npad_value: Optional[float],
    description: Optional[str],
) -> Optional[float]:
    """Alias for get_reliable_floor_area."""
    return get_reliable_floor_area(npad_value, description)


def reconcile_units(
    npad_value: Optional[int],
    description: Optional[str],
) -> Optional[int]:
    """Alias for get_reliable_units."""
    return get_reliable_units(npad_value, description)
