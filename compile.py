#!/usr/bin/env python3

import argparse
import gpxpy
import srtm
import polyline
import json
import os
import hashlib

elevation_data = srtm.get_data(local_cache_dir="srtm_cache")

base_dir = os.path.dirname(os.path.realpath(__file__))
gpx_dir = os.path.join(base_dir, "gpx")
generated_dir = os.path.join(base_dir, "generated")


def process_gpx(gpx_filepath, height_max_len=100):
    out_dict = {}

    with open(gpx_filepath, "rt") as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    out_dict["name"] = gpx.name
    out_dict["description"] = gpx.description
    out_dict["author"] = gpx.author_name

    tags = gpx.keywords
    if tags is not None:
        tags = [t.rstrip().lstrip() for t in tags.split(",")]
    out_dict["tags"] = tags

    gpx.remove_elevation()
    gpx.remove_time()

    points = []
    heights = []
    for seg in sum([track.segments for track in gpx.tracks], []) + gpx.routes:
        points += [(p.latitude, p.longitude, p.elevation) for p in seg.points]
    points2d = [p[:2] for p in points]

    gpx.tracks = []
    gpx.routes = []
    gpx.routes.append(gpxpy.gpx.GPXRoute(gpx.name, gpx.description))
    gpx.routes[0].points = [gpxpy.gpx.GPXRoutePoint(*p) for p in points]

    out_dict["polyline"] = polyline.encode(points2d)
    out_dict["length"] = gpx.routes[0].length()

    elevation_data.add_elevations(gpx.routes[0])
    heights = [p.elevation for p in gpx.routes[0].points]
    if len(heights) > height_max_len:
        heights = heights[:: len(heights) // height_max_len]
    out_dict["heights"] = heights

    utf8_polylines = json.dumps(out_dict["polyline"]).encode("UTF-8")
    walk_id = hashlib.sha1(utf8_polylines).hexdigest()[:6]
    out_dict["id"] = walk_id
    out_dict["filename"] = os.path.join("gpx", "route_" + walk_id + ".gpx")

    new_gpx_filepath = os.path.join(base_dir, out_dict["filename"])
    os.makedirs(os.path.dirname(new_gpx_filepath), exist_ok=True)
    with open(new_gpx_filepath, "wt") as new_gpx_file:
        new_gpx_file.write(gpx.to_xml())

    if os.path.abspath(new_gpx_filepath) != os.path.abspath(gpx_filepath):
        os.remove(gpx_filepath)

    return out_dict


if __name__ == "__main__":
    description = "Process multiple gpx files into a single polyline file"

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "gpxs", metavar="gpx", nargs="*", help="A list of gpx files to process"
    )

    args = parser.parse_args()

    gpxs = [os.path.join(gpx_dir, gpx) for gpx in os.listdir(gpx_dir)]
    gpxs += args.gpxs

    os.makedirs(generated_dir, exist_ok=True)
    os.makedirs(gpx_dir, exist_ok=True)
    output = []

    for gpx in gpxs:
        output.append(process_gpx(gpx))

    output = json.dumps(output).encode("UTF-8")

    output_filepath = os.path.join(generated_dir, "data.json")
    with open(output_filepath, "wb") as output_file:
        output_file.write(output)
