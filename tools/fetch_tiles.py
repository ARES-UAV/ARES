"""
Download the OpenStreetMap tiles the dashboard map needs, for offline use.

    python tools/fetch_tiles.py

WHY THIS EXISTS
    Demo-day constraint 3 in CLAUDE.md: map tiles need internet and venue wifi
    fails. Discovering that on 5 September is not a plan. This pulls the tiles
    covering the demo area onto disk ahead of time; the backend then serves
    them from `GET /tiles/{z}/{x}/{y}.png` and Leaflet never talks to
    openstreetmap.org during the demo.

WHAT IT COVERS
    A square box centred on the GPS origin in `backend/config.py`, 1 km on a
    side by default, at zoom 14 through 19. The origin is read from the config
    module rather than restated here, so moving the demo clip's origin moves
    the bundled tiles with it — re-run this and the map follows.

    The drone's assumed track (DRONE_SPEED_MS, DRONE_HEADING_DEG) runs out from
    that origin, so the box has to contain the track, not just its start. At
    5 m/s a clip would have to run past 100 seconds before it left a 1 km box.
    A longer clip or a faster track needs a bigger `--km`; the tool prints the
    box it used so the number is checkable rather than assumed.

BEING A GOOD CITIZEN
    OSM's tile servers are donated infrastructure and its usage policy asks
    bulk downloaders to identify themselves and go easy. So: a User-Agent
    naming this project and its repo, one request at a time with a delay
    between them, and tiles already on disk are never re-requested — a re-run
    after adding a zoom level costs only the new tiles.

    The default box is a few hundred tiles. Do not point this at a city.
"""

import argparse
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator, List, Tuple

# tools/ is a script directory, not a package, so the repo root is not on the
# path when this is run directly. Put it there before importing the backend.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402

# Identifies the project and gives a tile-server operator somewhere to look if
# this ever misbehaves. OSM rejects requests with a default or absent
# User-Agent, and it is the minimum courtesy for using someone else's bandwidth.
USER_AGENT = (
    "ARES-dashboard-tile-fetch/1.0 "
    "(disaster-response student project; "
    "+https://github.com/dewangdhakad/ARES)"
)

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# OSM renders nothing past 19. Asking for 20 gets 404s, not sharper tiles —
# see MAP_MAX_NATIVE_ZOOM in frontend/src/config.js, which is the same ceiling
# stated on the Leaflet side.
MAX_OSM_ZOOM = 19

DEFAULT_BOX_KM = 1.0
DEFAULT_MIN_ZOOM = 14
DEFAULT_MAX_ZOOM = 19
DEFAULT_DELAY_S = 0.5

# Metres per degree of latitude. The same constant `backend/localize.py` works
# in, and at this scale the spherical-earth error is far smaller than a tile.
METRES_PER_DEGREE_LAT = 111320.0


def deg2tile(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Slippy-map tile indices containing a coordinate, at one zoom level.

    The Web Mercator convention: x increases eastward, y increases SOUTHWARD.
    That y flip is the same reversal `localize.py` warns about going the other
    way, and getting it wrong here fetches a box that misses the survivors.
    """
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def bounding_box(
    lat: float, lon: float, box_km: float
) -> Tuple[float, float, float, float]:
    """A square box of `box_km` on a side, centred on a coordinate.

    Returns `(south, west, north, east)` in degrees.
    """
    half_m = box_km * 1000.0 / 2.0
    dlat = half_m / METRES_PER_DEGREE_LAT
    dlon = half_m / (METRES_PER_DEGREE_LAT * math.cos(math.radians(lat)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def tiles_in_box(
    south: float, west: float, north: float, east: float, zoom: int
) -> Iterator[Tuple[int, int, int]]:
    """Every `(z, x, y)` tile overlapping a bounding box at one zoom level."""
    # North edge gives the SMALLER y, because tile y grows southward.
    x_min, y_min = deg2tile(north, west, zoom)
    x_max, y_max = deg2tile(south, east, zoom)
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            yield zoom, x, y


def fetch_tile(z: int, x: int, y: int, destination: Path, timeout: float) -> None:
    """Download one tile to disk.

    Written to a temporary neighbour and renamed, so an interrupted run leaves
    no half-written PNG behind for the next run to skip as if it were complete.
    """
    request = urllib.request.Request(
        TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".png.part")
    partial.write_bytes(payload)
    partial.replace(destination)


def human_size(total_bytes: int) -> str:
    """Byte count as something readable in a terminal."""
    size = float(total_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download OpenStreetMap tiles around the configured demo origin "
            "into backend/data/tiles/ for offline use."
        )
    )
    parser.add_argument(
        "--km",
        type=float,
        default=DEFAULT_BOX_KM,
        help=f"side length of the square box, in km (default {DEFAULT_BOX_KM})",
    )
    parser.add_argument(
        "--min-zoom",
        type=int,
        default=DEFAULT_MIN_ZOOM,
        help=f"lowest zoom level to fetch (default {DEFAULT_MIN_ZOOM})",
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=DEFAULT_MAX_ZOOM,
        help=f"highest zoom level to fetch (default {DEFAULT_MAX_ZOOM})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_S,
        help=(
            "seconds to wait between requests (default "
            f"{DEFAULT_DELAY_S}). Only applied to tiles actually fetched."
        ),
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="per-request timeout in seconds"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=config.TILES_DIR,
        help="tile directory (default backend/data/tiles)",
    )
    args = parser.parse_args()

    if args.min_zoom > args.max_zoom:
        parser.error("--min-zoom cannot be greater than --max-zoom")
    if args.max_zoom > MAX_OSM_ZOOM:
        parser.error(
            f"OpenStreetMap renders no tiles past zoom {MAX_OSM_ZOOM}; "
            f"--max-zoom {args.max_zoom} would only fetch 404s"
        )
    if args.km <= 0:
        parser.error("--km must be positive")

    lat, lon = config.ORIGIN_LAT, config.ORIGIN_LON
    south, west, north, east = bounding_box(lat, lon, args.km)

    wanted = [
        tile
        for zoom in range(args.min_zoom, args.max_zoom + 1)
        for tile in tiles_in_box(south, west, north, east, zoom)
    ]

    print(f"Origin      {lat:.6f}, {lon:.6f}  (backend/config.py)")
    print(f"Box         {args.km} km square — {south:.6f},{west:.6f} to {north:.6f},{east:.6f}")
    print(f"Zoom        {args.min_zoom}-{args.max_zoom}")
    print(f"Tiles       {len(wanted)} in box")
    print(f"Destination {args.out}")
    print()

    downloaded = skipped = 0
    failures: List[str] = []

    for index, (z, x, y) in enumerate(wanted, start=1):
        destination = args.out / str(z) / str(x) / f"{y}.png"
        if destination.exists():
            skipped += 1
            continue

        # One at a time, with a pause. Deliberately not parallel: the point is
        # to be unremarkable to a donated tile server, not to finish fastest.
        if downloaded:
            time.sleep(args.delay)

        try:
            fetch_tile(z, x, y, destination, args.timeout)
        except (urllib.error.URLError, OSError) as exc:
            failures.append(f"{z}/{x}/{y}: {exc}")
            print(f"  [{index}/{len(wanted)}] {z}/{x}/{y} FAILED — {exc}")
            continue

        downloaded += 1
        print(f"  [{index}/{len(wanted)}] {z}/{x}/{y}")

    # Counted over the whole directory, not just this run's downloads: what
    # matters on 5 September is what is on disk, and a re-run that skipped
    # everything should still report the full bundle.
    on_disk = sorted(args.out.rglob("*.png")) if args.out.exists() else []
    total_bytes = sum(path.stat().st_size for path in on_disk)

    print()
    print(f"Downloaded  {downloaded}")
    print(f"Skipped     {skipped} (already on disk)")
    if failures:
        print(f"Failed      {len(failures)}")
        for failure in failures[:10]:
            print(f"  {failure}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more")
    print(f"On disk     {len(on_disk)} tiles, {human_size(total_bytes)} in {args.out}")

    if failures:
        print()
        print("Re-run to retry the failures — tiles already fetched are skipped.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
