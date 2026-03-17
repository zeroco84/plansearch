"""ITM (Irish Transverse Mercator) to WGS84 coordinate conversion."""

from pyproj import Transformer

# Create a singleton transformer: ITM (EPSG:2157) → WGS84 (EPSG:4326)
_transformer = Transformer.from_crs("EPSG:2157", "EPSG:4326", always_xy=True)


def itm_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert ITM coordinates to WGS84 latitude/longitude.

    Args:
        easting: ITM easting value
        northing: ITM northing value

    Returns:
        Tuple of (latitude, longitude) in WGS84
    """
    lng, lat = _transformer.transform(easting, northing)
    return lat, lng


def is_valid_dublin_coords(lat: float, lng: float) -> bool:
    """Check if coordinates are roughly in the Dublin area.

    Dublin is approximately: lat 53.2-53.5, lng -6.5 to -6.0
    """
    return 53.0 <= lat <= 53.6 and -6.6 <= lng <= -5.9
