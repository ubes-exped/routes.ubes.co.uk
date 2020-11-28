[routes.ubes.co.uk](https://routes.ubes.co.uk)
=================

Central repository for the routes.ubes.co.uk project. Provides hosting for the
gpx files, and compiled data that is used for generating the site.

Adding new routes
-----------------

To add a new route, all that is required is a gpx file of the route. The file
must have some metadata in it:

* `<name>` - The name of the route
* `<desc>` - A short description of the route

Optionally add the following tags:

* `<author>` - The person or persons who created the route
* `<keywords>` - Any keyword tags that you think might describe the route, separated by commas.

This gpx file should then be added to the [gpx](gpx) directory.

Compilation
-----------

The compilation step is done by running [compile.py](compile.py), which will
compile all gpx files in the [gpx](gpx) directory and also any gpx files
supplied as command-line argumanets.

The compilation step is automatically performed when new commits are pushed to
this repo, via a github action.

The compilation step takes the provided gpx file, adds/replaces the heights
using [SRTM.py](https://pypi.org/project/SRTM.py), and then renames the file to
a standard form derived from the hash of the polyline of the route.

From each of the standardised gpx files in the [gpx](gpx) directory a json
dictionary is created, which contains:

* The `name` for the route
* The `description` of the route
* An `id` derived from the hash of the combined segments
* The relative path to the `filename` of the gpx route (from the repo root)
* The `author` of the route
* A list of `tags` that apply to the route
* for each of the `segments` in the file:
* A `polyline` of the route
* A `length` of the route
* An `ele` polyline of the route, plotting elevation against distance instead
  of longitude against latitude. These two dimensions are both given in
  hundreds of kilometres (10⁵ metres) instead of degrees, so that the encoded
  polyline algorithm can store them as efficiently as possible with a
  resolution of one metre.

These json dictionaries are then concatenated to create
[walks.json](walks.json).
