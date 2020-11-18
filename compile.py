import argparse
import gpxpy
import srtm
import polyline
import json
import numpy as np
import os
import hashlib

elevation_data = srtm.get_data(local_cache_dir='srtm_cache')

base_dir = os.path.dirname(os.path.realpath(__file__))

def process_gpx(gpx_filepath, height_max_len=100):
    out_dict = {}

    with open(gpx_filepath, 'rt') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    elevation_data.add_elevations(gpx)
    gpx.remove_time()

    out_dict['name'] = gpx.name
    out_dict['description'] = gpx.description
    out_dict['routes'] = []

    for route in gpx.routes + gpx.tracks:
        route.remove_time()
        out_route = {'points': [],
                     'heights' : [],
                    }

        for seg in route.segments:
            points = [(p.latitude, p.longitude) for p in seg.points]
            out_route['points'] += points
            out_route['heights'] = [p.elevation for p in seg.points]

        out_route['points'] = polyline.encode(out_route['points'])

        height_len = len(out_route['heights'])
        if height_len > height_max_len:
            out_route['heights'] = out_route['heights'][::height_len // height_max_len]

        out_dict['routes'].append(out_route)

    output_filename = hashlib.sha1(json.dumps(out_dict['routes']).encode('UTF-8')).hexdigest()[10:]
    out_dict['filename'] = os.path.join('gpx_cache', output_filename + '.gpx')

    new_gpx_filepath = os.path.join(base_dir, out_dict['filename'])
    os.makedirs(os.path.dirname(new_gpx_filepath), exist_ok=True)
    with open(new_gpx_filepath, 'wt') as new_gpx_file:
        new_gpx_file.write(gpx.to_xml())

    return out_dict, output_filename

if __name__ == '__main__':
    description = 'Process multiple gpx files into a single polyline file'

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('gpxs', metavar='gpx', nargs='*',
                        help='A list of gpx files to process')

    args = parser.parse_args()
    gpxs = args.gpxs

    gpxs += [os.path.join(base_dir, 'gpx_cache', gpx) for gpx in
             os.listdir((os.path.join(base_dir, 'gpx_cache')))]

    data_dir = os.path.join(base_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)

    for gpx in gpxs:
        gpx_filepath = os.path.abspath(gpx)

        output, output_filename = process_gpx(gpx_filepath)
        output = json.dumps(output).encode('UTF-8')

        output_filepath = os.path.join(data_dir, output_filename + '.json')
        with open(output_filepath, 'wb') as output_file:
            output_file.write(output)


    manifest_filepath = os.path.join(base_dir, 'manifest.txt')

    with open(manifest_filepath, 'wt') as manifest_file:
        manifest = [ os.path.join('data',filename) + '\n' for filename in os.listdir(data_dir)]
        manifest_file.writelines(manifest)


