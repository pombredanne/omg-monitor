# OMG Monitor

[![Code Health](https://landscape.io/github/cloudwalkio/omg-monitor/master/landscape.png)](https://landscape.io/github/cloudwalkio/omg-monitor/master)

[![Docker build](http://dockeri.co/image/cloudwalk/monitor)](https://registry.hub.docker.com/u/cloudwalk/monitor/)

This program uses [NuPIC] to catch anomalies in streams of data. It runs as a [Docker] container, so to use it you just have to run the container with proper configuration files (see [Usage](#usage)).

Currently we support the following streams for input:
* [Pingdom]: Fetch response time data from pingdom and learn from it.
* [Librato]: Learn from any AWS EC2 metric (possibly any arbitrary metric will work)
* Dynamic: Push in any timeseries data via JSON and HTTP

Here is a simplified flowchart of the project:

![flowchart](https://rawgithub.com/cloudwalkio/omg-monitor/master/docs/images/new-omg-monitor.svg)

## Streams

A stream, basically, implements an abstract Python class with methods to gather historical data and real-time data. Those methods should return lists of pairs contained in dictionaries, like that: `[{'value': 123, 'time': datetime(...)}, {'value': 122, 'time': datetime(...)}]`. The `value` field is feed into NuPIC for anomaly detection.

As example, we can have the following values:

* Pingdom: Response time in ms.
* Librato: AWS.EC2.CPUUtilization in %.

## Monitor

A monitor is composed by a stream and a NuPIC model that fed into that stream.

The script `monitor/run_monitor.py` reads a configuration YAML file and starts batches of monitors according to the configuration.
`monitor/run_monitor_dyn.py` runs a little http endpoint allowing you to "push" in event data (vs pulling it from other streams).


### Configuration files

Configurations files are similar in many aspects, the main difference being the credentails section, as the need credentials can be different for different streams. You can notice the difference in the following templates.

An important point is in regard with the `monitors` section, which may be ommited for any configuration file, in which case it will start monitors for every stream availabe of that type. For example, for Pingdom, it will start a monitor for each check found under the given credentials.

We provide templates files for Pingdom and Librato in [monitor/config_templates/].

If you are using the dyanmic http event input - you don't need any config file (as the configuration data comes along with the data you push in).

## Output

Each monitor's NuPIC model calculates an anomaly score and an anomaly likelihood for each input, which are stored with some input fields in a [Redis] server. The data stored in Redis are lists of strings of the form `"time,actual,predicted,anomaly,likelihood"` with keys of the form `"results:[ID]"`.
It is also saved, for convenience, a name for the monitor in key `"name:[ID]"`, a label for the values being monitored in `"value_label:[ID]"` and a unit in `"value_unit:[ID]"`.

As a concrete example, if you start a monitor for a Pingdom check with `id = 123456`, it will save the keys `value_label:123456 "Response time` and `value_unit:1223456 "ms"`.

## Pushing in data

If you start the container with the parameter `-p 8080:8080 -e DYNAMIC=true` the app will listen on port 8080 for input data. This will create a monitor instance as needed - when a new check id comes in.
This allows you to pump in data from any event source at any pace.
As this all runs in the one process, this is slightly more memeory efficient.

### Example:

`make rebuild`

This will have an input endpoint listening on port 8080, to push in data:

```
curl --data '{"check_id": "check_id_here", "time":EPOCH_TIME, "value":42}' http://docker_host:8080
```
The first time it sees that check_id, a monitor instance will be created.
The time/value pair is the timeseries that is used as input.

The response will be a JSON object saying if the check is currently CRITICAL or OK.
You can of course use the API below to find out more information.

If you want to pass in non default options (eg resolution), add a config map:
`"config": {"name": "yeah"}` to the data you are inputting. resolution, webhook, anomaly_threshold, likelihood_threshold are the
most relevant ones. Defaults are generally fine. The unit, label and name are used for display purposes.

In the /examples directory are some helper scripts to test out this feature.

## API

The results can be accessed via a RESTful API written in [Go] using [Martini].

It is very simplistic:

* To get the monitors running:
```
GET /monitors
```
The JSON list returned is of the form:
```json
{
  "monitors": [
    {
      "id": "cw.us-east-xxx",
      "name": "Machine X",
      "value_label": "CPU utilization",
      "value_unit": "%"
    },
    {
      "id": "cw.us-east-yyy",
      "name": "Machine Y",
      "value_label": "CPU utilization",
      "value_unit": "%"
    },
    {
      "id": "123456",
      "name": "staging manager",
      "value_label": "Response time",
      "value_unit": "ms"
    },
    {
      "id": "654321",
      "name": "staging switch",
      "value_label": "Response time",
      "value_unit": "ms"
    }
  ]
}
```

* To get the last `[N]` results for `[ID]`:
```
GET /results/[ID]?limit=[N]
```
  The resulting JSON string has the following fields:
  * actual: actual value at the given time instant.
  * predicted: value prediction for the given time instant.
  * anomaly: the unlikelihood of the actual result in comparisson with the predicted result.
  * likelihood: the likelihood that the last anomaly score follows the historical probability distribution.
  * time: UNIX time when data was originally gathered.
  If no limit is specified it is assumed that `N=0`, so that the API returns all the results for the given `CHECK_ID`.

If we specify the option `-t SERVER_TOKEN` when starting the service, we should pass an `access_token=SERVER_TOKEN` argument to each API's call, otherwise the API will throw an `Not authorized` message. For example:
```
GET /monitors?access_token=SERVER_TOKEN
```

Note you can choose whatever string you like in place of `SERVER_TOKEN`.

## API Client

The Go server also serves static HTML files that uses [jQuery] to access our API to get the results and dinamically plot them. Currently we have three visualizations:

* The [index.html][2] file uses [D3.js] to plot the last hour results with anomalies.
* The [likelihood.html][3] file uses [D3.js] to plot the last hour results with anomalies likelihoods.
* The [gauge.html][1] file uses [justGage] to plot the latest anomalies likelihoods as gauge charts.

See the session [Screenshots](#screenshots) for some examples.

## Usage

With [Docker] installed, do:
```
sudo docker run -d -v /HOST/PATH/TO/CONFIG/FILES/:/CONTAINER/PATH/TO/CONFIG/FILES/ -p [PUBLIC_PORT]:5000 cloudwalk/monitor [-t SERVER_TOKEN] CONTAINER/PATH/TO/CONFIG/FILES/config1.yaml CONTAINER/PATH/TO/CONFIG/FILES/config2.yaml ...
```

As we must pass some configuration files to the container, we mount the host volume containing those files inside the container, passing the containers absolute path for the configuration files as an argument to the container.

We must pass at least one configuration file when starting the container and we can, optionally, pass a argument `--token SERVER_TOKEN` with a token to be used for access authentication of our API.

Other parameter that we must specify is the  `[PUBLIC_PORT]` used by the Go server.

## Log files

The logs generated by Redis, Martini and the monitors are saved in a directory specified by `LOG_DIR` environment variable, which defaults to `LOG_DIR=/var/log/docker/monitor`. To access the logs from the host, outside de container, we can mount a host directory to LOG_DIR when starting the container, using flag `-v`:
```
sudo docker run -d -v /HOST/PATH/TO/LOG/DIR:/var/log/docker/monitor -p [PUBLIC_PORT]:5000 cloudwalk/monitor [-t SERVER_TOKEN] CONTAINER/PATH/TO/CONFIG/FILES/config1.yaml CONTAINER/PATH/TO/CONFIG/FILES/config2.yaml ...
```

An alternative is to mount the volume from another container, using the `--volumes-from` flag.

## Q&A

### What happens when the container is started?

The Docker container entrypoint is the script [startup.sh], responsible for starting the Redis and Go servers and for running the [monitor/run_monitor.py] script, which will start one monitor instance for each ID in each stream configuration file, each one in a separate thread (running in parallel).

### How to build the image?

The above Docker command `run` will pull the image `cloudwalk/monitor` from [Docker index][docker_image]. That image is kept updated through Docker's Trusted Build feature.

To build the Docker image locally, clone this repository and do:

    sudo docker build -t "[USERNAME]/monitor" .

Note that our [Dockerfile] uses the [cloudwalk/nupic] image, as that image already contains a NuPIC installation. We don't use `numenta/nupic` as it is rapidly changing, so we prefer a frozen version of it

## Screenshots


![gauge](https://rawgithub.com/cloudwalkio/omg-monitor/master/docs/images/gauge.png)

![anomaly](https://rawgithub.com/cloudwalkio/omg-monitor/master/docs/images/anomaly.png)

![likelihood](https://rawgithub.com/cloudwalkio/omg-monitor/master/docs/images/likelihood.png)

License
-------
```
OMG Monitor
Copyright (C) 2014 CloudWalk Inc.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

```

[NuPIC]:https://github.com/numenta/nupic
[Docker]:https://www.docker.io/
[Pingdom]:https://www.pingdom.com/
[Librato]:https://metrics.librato.com/
[Redis]:http://redis.io/
[Martini]:https://github.com/codegangsta/martini
[Go]:http://golang.org/
[D3.js]:http://d3js.org/
[jQuery]:http://jquery.com/
[justGage]:http://justgage.com/
[python-restful-pingdom]:https://github.com/drcraig/python-restful-pingdom
[allanino/nupic]:https://github.com/allanino/docker-nupic
[monitor/config_templates/]:monitor/config_templates/
[Dockerfile]:https://github.com/allanino/omg-monitor/blob/master/Dockerfile
[monitor/run_monitor.py]:https://github.com/allanino/omg-monitor/blob/master/monitor/run_monitor.py
[startup.sh]:https://github.com/allanino/omg-monitor/blob/master/startup.sh
[docker_image]:https://index.docker.io/u/cloudwalk/monitor/
[2]:https://github.com/allanino/omg-monitor/blob/master/server/public/index.html
[1]:https://github.com/allanino/omg-monitor/blob/master/server/public/gauge.html
[3]:https://github.com/allanino/omg-monitor/blob/master/server/public/likelihood.html
