#!/usr/bin/env python

import os
from monitor import Monitor
import logging
import logging.handlers
import SocketServer
import BaseHTTPServer
import json
from datetime import datetime
from collections import deque
import time
import threading


# Use logging
logger = logging.getLogger(__name__)
handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/run_monitor.log",
                                               maxBytes=1024*1024,
                                               backupCount=4,
                                              )

formatter = logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s')
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# This will listen for pushed data
# If there is already a check monitor setup - it will use it and add data
# otherwise it will create a new monitor/model

# the current configured monitors - each one has a chunk of CLA memory
current_monitors = {}

# track the last time something was seen
last_seen_input = {}

# keep a list for moving average purposes
moving_averages = {}

def get_monitor(check_id, config):
    """ Get or create a new monitor with optional config """

    last_seen_input[check_id] = time.time()

    if check_id not in current_monitors:
        current_monitors[check_id] = new_monitor(check_id, config)
        moving_average_window = int(config.get('moving_average_window', 10))
        moving_averages[check_id] = deque([0.0] * moving_average_window, maxlen=moving_average_window)
    return (current_monitors[check_id], moving_averages[check_id])

def garbage_collect(timeout):
    """ Garbage collect checks that havent' seen action in a while to save memory """

    to_remove = []
    for check_id in last_seen_input:
        if (time.time() - last_seen_input[check_id] > timeout):
            to_remove.append(check_id)

    for check_id in to_remove:
        logger.info("Garbage collecting: %s", check_id)
        remove_monitor(check_id)


def gc_task():
    """ Schedule a regular clean out of garbage - if not seen for an hour will clean it out """

    def do_gc(cleanup_interval=60, timeout=3600):
        while True:
            garbage_collect(timeout)
            time.sleep(cleanup_interval)

    worker = threading.Thread(target=do_gc, args=[])
    worker.start()

def remove_monitor(check_id):
    """ Save some memory by clearing monitor - stopping nupic as well as redis storage """

    del last_seen_input[check_id]
    del moving_averages[check_id]
    mon = current_monitors[check_id]
    mon.delete()
    del current_monitors[check_id]

class Dynamic(object):
    """ Class to provide a stream of data to NuPIC. """

    @property
    def value_label(self):
        return self.label

    @property
    def value_unit(self):
        return self.unit

    def __init__(self, config):
        self.id = config['id']
        self.name = config['name']
        self.unit = config['unit']
        self.label = config['label']

def new_monitor(check_id, config):
    """ Return a new monitor with given check_id and config """

    # default config for any new checks
    # overridable by the first input to this check stream
    monitor_config = {'resolution': 10,
                      'seconds_per_request': 60,
                      'webhook': None,
                      'channel': None,
                      'likelihood_threshold': None,
                      'anomaly_threshold': 0.9,
                      'domain': 'localhost',
                      'protocol': 'http',
                      'nupic_model_params': {'spParams': {'maxBoost': 1.1}}}
    monitor_config.update(config)

    logger.info("Monitor configuration: %s", monitor_config)

    stream_config = {'id': check_id,
                     'name': check_id,
                     'unit': "unknown_unit",
                     'label' : "unknown_label"}
    stream_config.update(config)


    # Instantiate monitor
    logger.info("Instantiating monitor: %s", stream_config['name'])

    # Instantiate stream
    stream = Dynamic(stream_config)

    # Add stream to monitor configuration
    monitor_config['stream'] = stream

    # Instantiate monitor
    return Monitor(monitor_config)

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """ This is the http entrypoint for json data - streams created on the fly """

    def do_GET(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
        s.wfile.write("<html><head><title>Simple http data input.</title></head>")
        usage = """
        <body><p>Post here something like:
          <code>
           curl --data '{"check_id": "mic2", "time":4420, "value":42}' http://boot2docker:8080
          </code>
          And then look at boot2docker:5000 for plot
        <p>
        </body>
        """
        s.wfile.write(usage)
        s.wfile.write("</body></html>")

    def do_POST(s):
        varLen = int(s.headers['Content-Length'])
        postVars = s.rfile.read(varLen)
        req = json.loads(postVars)
        (monitor, averages) = get_monitor(req['check_id'], req.get('config', {}))
        averages.appendleft(req['value'])
        smoothValue = sum(averages)/len(averages)
        model_input = {'time': datetime.utcfromtimestamp(req['time']), 'value': smoothValue, 'raw_value': smoothValue}
        res = monitor.update(model_input, True)
        res['current_value'] = smoothValue
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        s.wfile.write(json.dumps(res))

    def do_DELETE(s):
        varLen = int(s.headers['Content-Length'])
        postVars = s.rfile.read(varLen)
        req = json.loads(postVars)
        check_id = req['check_id']
        remove_monitor(check_id)
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        s.wfile.write('{"result": "OK"}\n')

if __name__ == "__main__":
    port = 8080
    httpd = SocketServer.TCPServer(("", port), MyHandler)
    logger.info("Serving at port %d", port)
    gc_task()
    httpd.serve_forever()
