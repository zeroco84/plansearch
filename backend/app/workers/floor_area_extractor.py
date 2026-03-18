"""PlanSearch — Floor Area Extractor.

Extracts floor area from planning application description text
and cross-checks against the NPAD FloorArea field.

When NPAD FloorArea disagrees with the description, the description wins.
"""

import re
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Conversion factors
SQ_FT_TO_SQ_M = 0.09290304

# Patterns for area extraction
# Matches: 16,386sq.m. | 975 sq.m. | 16386 m² | 7376 sqm | 16,386 square metres
# Also: 176,000 sq.ft. | 1,892 sq ft | 5000 sq. ft.
_NUM_PATTERN = r"([\d,]+(?:\.\d+)?)"

_AREA_PATTERNS = [
    # sq.m. / sq m / sqm / m² — square metres
    re.compile(
        _NUM_PATTERN + r"\s*(?:sq\.?\s*m\.?|sqm|m²|m2|square\s*met(?:re|er)s?)",
        re.IGNORECASE,
    ),
    # sq.ft. / sq ft / sqft / ft² — square feet (convert to m²)
    re.compile(
        _NUM_PATTERN + r"\s*(?:sq\.?\s*ft\.?|sqft|ft²|square\s*(?:foot|feet))",
        re.IGNORECASE,
    ),
]

# Patterns for residential unit counts
_UNIT_PATTERNS = [
    # "45 residential units" | "120 apartments" | "200 dwelling units"
    re.compile(
        _NUM_PATTERN + r"\s*(?:no\.?\s*)?(?:residential\s+units?|apartments?|dwelling\s+units?|dwellings?|houses?|units?\s+(?:of\s+)?accommodation)",
        re.IGNORECASE,
    ),
    # "comprising 45 units" | "of 120 units" | "containing 200 units"
    re.compile(
        r"(?:comprising|containing|of|totalling|total(?:ing)?)\s+" + _NUM_PATTERN + r"\s*(?:no\.?\s*)?(?:units?|beds?)",
        re.IGNORECASE,
    ),
]


def _parse_number(s: str) -> float:
    """Parse a number string, removing commas."""
    return float(s.replace(",", ""))


def extract_areas_from_text(description: str) -> List[Tuple[float, str]]:
    """Extract all floor area mentions from description text.

    Returns list of (area_m2, raw_match) tuples.
    """
    if not description:
        return []

    results = []

    # Square metres
    for match in _AREA_PATTERNS[0].finditer(description):
        try:
            area = _parse_number(match.group(1))
            if area > 0:
                results.append((area, match.group(0).strip()))
        except (ValueError, IndexError):
            continue

    # Square feet → convert to m²
    for match in _AREA_PATTERNS[1].finditer(description):
        try:
            area_ft = _parse_number(match.group(1))
            if area_ft > 0:
                area_m2 = area_ft * SQ_FT_TO_SQ_M
                results.append((area_m2, match.group(0).strip()))
        except (ValueError, IndexError):
            continue

    return results


def extract_total_floor_area(description: str) -> Optional[float]:
    """Extract the total/largest floor area from a description.

    Strategy:
    - Extract all area mentions
    - The largest value is typically the total GFA
    - Ignore very small values (<5 m²) which are likely room dimensions
    """
    areas = extract_areas_from_text(description)
    if not areas:
        return None

    # Filter out tiny values (room dimensions, sign sizes, etc.)
    significant = [a for a, _ in areas if a >= 5.0]
    if not significant:
        return None

    # The largest area mentioned is typically the total
    return max(significant)


def extract_unit_count(description: str) -> Optional[int]:
    """Extract residential unit count from description text."""
    if not description:
        return None

    for pattern in _UNIT_PATTERNS:
        for match in pattern.finditer(description):
            try:
                count = int(_parse_number(match.group(1)))
                if 1 <= count <= 10_000:
                    return count
            except (ValueError, IndexError):
                continue

    return None


def reconcile_floor_area(
    npad_value: Optional[float],
    description: Optional[str],
) -> Optional[float]:
    """Cross-check NPAD FloorArea against the description text.

    Rules:
    1. If description has a floor area and NPAD doesn't → use description
    2. If NPAD has a value and description doesn't → use NPAD (if sane)
    3. If both exist and agree (within 20%) → use NPAD (more precise)
    4. If both exist and disagree → use description (more trustworthy)
    5. Hard cap: 500,000 m² (anything above is clearly bad data)
    """
    desc_area = extract_total_floor_area(description) if description else None

    # Neither source has data
    if not npad_value and not desc_area:
        return None

    # Only description has data
    if not npad_value or npad_value <= 0:
        if desc_area and desc_area <= 500_000:
            return desc_area
        return None

    # Only NPAD has data — apply sanity check
    if not desc_area:
        if npad_value <= 500_000:
            return npad_value
        # NPAD value is absurd, reject it
        logger.warning(
            f"NPAD FloorArea {npad_value:,.0f} exceeds 500k m² with no description to verify — rejecting"
        )
        return None

    # Both exist — compare
    ratio = npad_value / desc_area if desc_area > 0 else float("inf")

    if 0.8 <= ratio <= 1.2:
        # Within 20% — they agree, use NPAD (likely more precise)
        return npad_value

    # They disagree — description wins
    logger.info(
        f"FloorArea mismatch: NPAD={npad_value:,.0f} vs description={desc_area:,.0f} "
        f"(ratio {ratio:.1f}x) — using description value"
    )
    return desc_area if desc_area <= 500_000 else None


def reconcile_units(
    npad_value: Optional[int],
    description: Optional[str],
) -> Optional[int]:
    """Cross-check NPAD NumResidentialUnits against the description text."""
    desc_units = extract_unit_count(description) if description else None

    if not npad_value and not desc_units:
        return None

    if not npad_value or npad_value <= 0:
        return desc_units

    if not desc_units:
        return npad_value if npad_value <= 10_000 else None

    # Both exist — compare
    if npad_value == desc_units:
        return npad_value

    ratio = npad_value / desc_units if desc_units > 0 else float("inf")
    if 0.8 <= ratio <= 1.2:
        return npad_value

    # Disagree — description wins
    logger.info(
        f"Unit count mismatch: NPAD={npad_value} vs description={desc_units} — using description"
    )
    return desc_units
