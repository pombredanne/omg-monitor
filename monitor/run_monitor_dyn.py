#!/usr/bin/env python

import sys
import os
from monitor import Monitor
import logging
import logging.handlers
import yaml
import importlib
import SimpleHTTPServer
import SocketServer
import BaseHTTPServer
import json
from datetime import datetime

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

current_monitors = {}

# listen for web requests - when one hits - check name in current.
# If there - pull out the WebMonitor and call update() - check response...
# If not - create new WebMonitor

def get_monitor(check_id):
    if not check_id in current_monitors:
      current_monitors[check_id] = new_monitor(check_id)
    return current_monitors[check_id]

class Dynamic():
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




def new_monitor(check_id):

    # default config for any new checks
    # Get configurations to pass to monitor class
    monitor_config = {'resolution': 2,
                      'seconds_per_request': 60,
                      'webhook': 'http://localhost/listening',
                      'likelihood_threshold': 0.9,
                      'anomaly_threshold': 0.9}
    logger.info("Monitor configuration: %s", monitor_config)

    stream_config = {'id': check_id,
                     'name': 'any stream name - eg librato',
                     'unit': "UNIT",
                     'label' : "LABEL"}

    # Instantiate monitor
    logger.info("Instantiating monitor: %s", stream_config['name'])

    # Instantiate stream
    stream = Dynamic(stream_config)

    # Add stream to monitor configuration
    monitor_config['stream'] = stream

    # Instantiate monitor
    return Monitor(monitor_config)





class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
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
        monitor = get_monitor(req['check_id'])
        model_input = {'time': datetime.utcfromtimestamp(req['time']), 'value': req['value']}
        if monitor._update(model_input, True):
          res = "CRITICAL"
        else:
          res = "OK"
        s.send_response(200)
        s.send_header("Content-type", "application/json")
        s.end_headers()
        s.wfile.write('{"result": "%s"}' % res)






if __name__ == "__main__":
  PORT=8080
  httpd = SocketServer.TCPServer(("", PORT), MyHandler)
  print "serving at port", PORT
  httpd.serve_forever()
