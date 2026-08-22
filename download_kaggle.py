import urllib.request
import os

print("Downloading sample nadir GeoTIFF files...")

urls = [
    # A small extract of Landsat imagery (RGB)
    ("https://raw.githubusercontent.com/rasterio/rasterio/master/tests/data/RGB.byte.tif", "sample_nadir_1.tif"),
    # A small single-band test GeoTIFF
    ("https://raw.githubusercontent.com/OSGeo/gdal/master/autotest/gcore/data/byte.tif", "sample_nadir_2.tif")
]

for url, filename in urls:
    if not os.path.exists(filename):
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url, filename)
        print(f"Saved to {filename}")
    else:
        print(f"{filename} already exists.")

print("Done! You can now use these GeoTIFF files to test geographic mapping.")
