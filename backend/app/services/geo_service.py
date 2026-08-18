import os
import rasterio
from rasterio.crs import CRS
from rasterio.errors import CRSError
from pyproj import Transformer, Proj
from shapely.geometry import shape, mapping, box, Polygon
from shapely.ops import transform
from typing import Dict, Any, Tuple, Optional

class GeoServiceException(Exception):
    pass

class GeoService:
    @staticmethod
    def read_raster_metadata(file_path: str) -> Dict[str, Any]:
        """Read essential metadata from a geospatial raster."""
        if not os.path.exists(file_path):
            raise GeoServiceException(f"File not found: {file_path}")
            
        with rasterio.open(file_path) as src:
            return {
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "crs": src.crs,
                "transform": src.transform,
                "bounds": src.bounds,
                "resolution": src.res,
                "driver": src.driver,
                "nodata": src.nodata
            }

    @staticmethod
    def validate_crs(crs: Optional[CRS]) -> str:
        """Confirm a valid CRS exists and return its string representation (e.g., EPSG code)."""
        if crs is None:
            raise GeoServiceException("The uploaded geospatial image does not contain a valid CRS.")
        
        try:
            # Try to get EPSG code if available, otherwise WKT
            if crs.is_epsg_code:
                return f"EPSG:{crs.to_epsg()}"
            return crs.to_wkt()
        except CRSError:
            raise GeoServiceException("Invalid CRS format in geospatial image.")

    @staticmethod
    def raster_bounds(file_path: str) -> Polygon:
        """Calculate true geographic bounds (EPSG:4326) from the actual raster metadata."""
        meta = GeoService.read_raster_metadata(file_path)
        crs_str = GeoService.validate_crs(meta["crs"])
        
        # Create a bounding box polygon in the source CRS
        src_bounds = meta["bounds"]
        geom_box = box(src_bounds.left, src_bounds.bottom, src_bounds.right, src_bounds.top)
        
        # Transform to EPSG:4326
        return GeoService.transform_geometry(geom_box, crs_str, "EPSG:4326")

    @staticmethod
    def pixel_to_world(pixel_x: float, pixel_y: float, transform) -> Tuple[float, float]:
        """Convert pixel coordinates to world coordinates using actual affine transform."""
        # transform * (x, y) returns (lon, lat) or (easting, northing) in source CRS
        return transform * (pixel_x, pixel_y)

    @staticmethod
    def transform_geometry(geom: Polygon, src_crs: str, dst_crs: str) -> Polygon:
        """Transform a Shapely geometry from one CRS to another."""
        if src_crs == dst_crs:
            return geom
            
        project = Transformer.from_crs(src_crs, dst_crs, always_xy=True).transform
        return transform(project, geom)

    @staticmethod
    def choose_metric_crs(geom: Polygon) -> str:
        """
        Create a clear CRS utility for choosing an appropriate metric projection.
        Calculates a dynamic UTM zone based on the geometry's centroid (assumes input is EPSG:4326).
        """
        centroid = geom.centroid
        lon, lat = centroid.x, centroid.y
        
        # Calculate UTM zone from longitude
        zone_number = int((lon + 180) / 6) + 1
        
        # Determine hemisphere (North/South)
        hemisphere = 'N' if lat >= 0 else 'S'
        
        # Proj string for Dynamic UTM
        return f"+proj=utm +zone={zone_number} +{'north' if hemisphere == 'N' else 'south'} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"

    @staticmethod
    def geometry_to_geojson(geom: Polygon) -> Dict[str, Any]:
        """Convert a Shapely geometry to a GeoJSON dictionary."""
        return mapping(geom)

    @staticmethod
    def validate_geometry(geom_dict: Dict[str, Any]) -> Polygon:
        """Parse and validate a GeoJSON geometry dictionary into a Shapely geometry."""
        try:
            geom = shape(geom_dict)
            if not geom.is_valid:
                geom = geom.buffer(0) # Attempt to repair
                if not geom.is_valid:
                    raise GeoServiceException("Invalid geometry could not be repaired.")
            return geom
        except Exception as e:
            raise GeoServiceException(f"Failed to parse geometry: {str(e)}")

