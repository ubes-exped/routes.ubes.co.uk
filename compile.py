import argparse
import gpxpy
import srtm
import polyline
import json
import os
import hashlib

elevation_data = srtm.get_data(local_cache_dir='srtm_cache')

base_dir = os.path.dirname(os.path.realpath(__file__))
gpx_dir  = os.path.join(base_dir, "gpx")
data_dir = os.path.join(base_dir, "data")

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
    out_dict['filename'] = os.path.join('gpx', output_filename + '.gpx')

    new_gpx_filepath = os.path.join(base_dir, out_dict['filename'])
    os.makedirs(os.path.dirname(new_gpx_filepath), exist_ok=True)
    with open(new_gpx_filepath, 'wt') as new_gpx_file:
        new_gpx_file.write(gpx.to_xml())

    return out_dict

if __name__ == '__main__':
    description = 'Process multiple gpx files into a single polyline file'

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('gpxs', metavar='gpx', nargs='*',
                        help='A list of gpx files to process')

    args = parser.parse_args()

    gpxs = args.gpxs
    gpxs += [os.path.join(gpx_dir, gpx) for gpx in os.listdir(gpx_dir)]

    os.makedirs(data_dir, exist_ok=True)
    output = []

    for gpx in gpxs:
        output.append(process_gpx(gpx))

    output = json.dumps(output).encode('UTF-8')

    output_filepath = os.path.join(base_dir, 'generated', 'data.json')
    with open(output_filepath, 'wb') as output_file:
        output_file.write(output)

