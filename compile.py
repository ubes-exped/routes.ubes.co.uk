#!/usr/bin/env python3

import argparse
import gpxpy
import srtm
import polyline
import json
from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin
import os
import itertools
import shutil
import hashlib
import traceback
import sys
from typing import TypedDict, List, Any, Tuple, Optional
from timeit import default_timer as timer

with open("CNAME", "r") as cname_file:
    cname = cname_file.read().strip()
    url_base = "https://" + cname

elevation_data = srtm.get_data(local_cache_dir="srtm_cache")

base_dir = os.path.dirname(os.path.realpath(__file__))
gpx_dir = os.path.join(base_dir, "gpx")
generated_dir = os.path.join(base_dir, "generated")


@dataclass
class Walk(DataClassJsonMixin):
    id: str
    filename: str
    name: Optional[str]
    description: Optional[str]
    author: Optional[str]
    tags: List[str]

    length: int
    """Length of the route in metres"""

    ascent: int
    """Total ascent of the route in metres"""

    polyline: str
    """Encoded polyline of lat/long values"""

    ele: str
    """Encoded polyline of lat/long values"""

    def __init__(self):
        """Override the dataclass constructor requiring all arguments"""
        pass


def write_json(file_path: str, data: Walk):
    """Write an arbitrary object as JSON to a file

    Args:
        file_path (str): The relative path to the file
        json (any): The JSON data to write
    """

    output = data.to_json(separators=(",", ":")).encode("UTF-8")

    with open(file_path, "wb") as file:
        file.write(output)


def elevation_summary(
    points: List[gpxpy.gpx.GPXRoutePoint], route_length: int, count: int
) -> Tuple[int, str]:

    elapsed_distance = 0

    points_with_elevation = [point for point in points if point.elevation]

    elevations: List[Tuple[float, float]] = []
    """List[(dist, ele)], each given in hundreds of kilometres so they are efficiently encoded as polylines to the nearest metre"""

    next_point = 0.0

    def add_elevation(dist_m: int, ele_m: int) -> float:
        """
        Add an elevation to the list of points.

        This returns the distance at which to take the next reading.
        """
        elevations.append((dist_m / 1e5, ele_m / 1e5))

        remaining_distance = route_length - elapsed_distance
        remaining_points = count - len(elevations)

        if remaining_points == 0:
            return float("inf")

        return elapsed_distance + remaining_distance / remaining_points

    next_point = add_elevation(0, points_with_elevation[0].elevation)
    ascent = 0

    for i, prev, curr in zip(itertools.count(), points_with_elevation, points_with_elevation[1:]):
        ascent += max(0, curr.elevation - prev.elevation)

        elapsed_distance += curr.distance_2d(prev)
        if elapsed_distance > next_point or i + 1 == len(points_with_elevation):
            next_point = add_elevation(elapsed_distance, curr.elevation)

    return ascent, polyline.encode(elevations)


def encode_polyline(points: List[gpxpy.geo.Location]) -> str:
    return polyline.encode([(p.latitude, p.longitude) for p in points])


def safe_strip(string: Optional[str]) -> Optional[str]:
    if string is None:
        return string
    return string.strip()


def process_gpx(gpx_filepath: str, elevations_max_len=100, simplification: int = 5):
    """
    Turn a GPX into a summary of the walk, normalising the file at the same time.

    Args:
        gpx_filepath (str): The path to a GPX file to process.
        elevations_max_len (int, optional): The maximum number of elevation data points to give.
        simplification (int, optional): The amount to simplify the line by, equivalent to maximum
            distance between the true points and the simplified line.
    """
    summary = Walk()

    with open(gpx_filepath, "rt") as gpx_file:
        gpx = gpxpy.parse(gpx_file, version="1.1")

    summary.name = safe_strip(gpx.name)
    summary.description = safe_strip(gpx.description)
    summary.author = safe_strip(gpx.author_name)

    tags = gpx.keywords
    if tags is not None:
        tags = [t.strip() for t in tags.split(",")]
        tags.sort()
    summary.tags = tags

    gpx.remove_elevation()
    gpx.time = None
    gpx.remove_time()

    points: List[gpxpy.gpx.GPXRoutePoint] = []
    elevations: List[int] = []
    for seg in itertools.chain(*(track.segments for track in gpx.tracks), gpx.routes):
        points.extend(
            gpxpy.gpx.GPXRoutePoint(p.latitude, p.longitude) for p in seg.points
        )

    gpx.tracks = []
    route = gpxpy.gpx.GPXRoute(gpx.name, gpx.description)
    gpx.routes = [route]
    route.points = points

    # Used for legacy reasons for creating a hash, and if simplification is disabled
    full_polyline = encode_polyline(points)

    if simplification != 0:
        simplified = gpxpy.geo.simplify_polyline(gpx.routes[0].points, simplification)

        summary.polyline = encode_polyline(simplified)
    else:
        summary.polyline = full_polyline

    summary.length = int(round(gpx.routes[0].length()))

    elevation_data.add_elevations(gpx.routes[0])

    summary.ascent, summary.ele = elevation_summary(
        gpx.routes[0].points, summary.length, elevations_max_len
    )

    utf8_polylines = json.dumps(full_polyline).encode("UTF-8")
    walk_id = hashlib.sha1(utf8_polylines).hexdigest()[:6]
    summary.id = walk_id
    gpx_filename = os.path.join("gpx", "route_" + walk_id + ".gpx")
    summary.filename = "/".join([url_base, gpx_filename])

    new_gpx_filepath = os.path.join(base_dir, gpx_filename)
    os.makedirs(os.path.dirname(new_gpx_filepath), exist_ok=True)
    with open(new_gpx_filepath, "wt") as new_gpx_file:
        new_gpx_file.write(gpx.to_xml())

    summary_file = os.path.join(generated_dir, "route_" + walk_id + ".json")
    write_json(summary_file, summary)

    if os.path.abspath(new_gpx_filepath) != os.path.abspath(gpx_filepath):
        os.remove(gpx_filepath)


def combine_json_files(output_file_path: str, input_dir: str):
    with open(output_file_path, "wb") as output_file:
        output_file.write(b"[\n")
        try:
            first_file = True
            for input_file_name in sorted(os.listdir(generated_dir)):

                if not first_file:
                    output_file.write(b",\n")
                else:
                    first_file = False

                input_file_path = os.path.join(generated_dir, input_file_name)
                with open(input_file_path, "rb") as input_file:
                    input = input_file.read()
                    output_file.write(input)

        finally:
            output_file.write(b"\n]")


if __name__ == "__main__":
    description = "Process multiple gpx files into a single polyline file"

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "gpxs", metavar="gpx", nargs="*", help="A list of gpx files to process"
    )

    args = parser.parse_args()

    if args.gpxs:
        gpxs = args.gpxs
    else:
        gpxs = [os.path.join(gpx_dir, gpx) for gpx in os.listdir(gpx_dir)]

    shutil.rmtree(generated_dir, ignore_errors=True)
    os.makedirs(generated_dir, exist_ok=True)
    os.makedirs(gpx_dir, exist_ok=True)

    for gpx in gpxs:
        start = timer()
        try:
            process_gpx(gpx)
            print(gpx, "processed in", timer() - start, "seconds")
        except Exception as e:
            print(gpx, "failed to process:", e, file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

    combined_file_path = os.path.join(base_dir, "walks.json")
    combine_json_files(combined_file_path, generated_dir)
