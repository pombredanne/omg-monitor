#!/usr/bin/env python

import sys
import os
import multiprocessing
from monitor import Monitor
from streams.pingdom import PingdomStream
import logging
import logging.handlers
import ConfigParser
import importlib

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

# Multiprocessing logger
multiprocessing.log_to_stderr(logging.DEBUG)

def run(StreamClass, stream_config, resolution):
    # Instantiate monitor
    logger.info("Stantiating monitor: %s", stream_config['name'])

    stream = StreamClass(stream_config)
    monitor = Monitor(resolution, stream)

    # Train monitor
    logger.info("Starting training: %s", stream_config['name'])
    monitor.train()
        
    # Enter loop for online learning
    logger.info("Going online: %s", stream_config['name'])
    monitor.loop()    

if __name__ == "__main__":
    if(len(sys.argv) < 2):
        logger.info("Usage: run_monitor.py [config.cfg]")
        sys.exit(0)
    
    config = ConfigParser.ConfigParser()
    config.read(sys.argv[1])
    
    stream_type= config.get('general', 'stream')

    stream_module = importlib.import_module("streams.%s" % stream_type)
    StreamClass = getattr(stream_module, "%sStream" % stream_type.title())

    # Set credentials dict
    credentials = {}
    for name, value in config.items('credentials'):
        credentials[name] = value

    try:
        streams = StreamClass.available_streams(credentials)
    except Exception, e:
        logger.error('Could not connect to stream.', exc_info=True)
        sys.exit(0)

    # Get parameters
    resolution = int(config.get('parameters', 'encoder_resolution'))
    moving_average_window = int(config.get('parameters', 'moving_average_window'))

    # If don't have specfied monitors, run everything!
    if not config.has_section('monitors'):
        # Start the monitors sessions
        jobs_list = []                    
        for stream in streams:
            stream_id = stream['id']
            stream_name = stream['name']
            
            logger.info("Starting stream: %s", stream_name)
            
            # Configuration to pass to stream class
            stream_config = {'id': stream_id, 
                             'name': stream_name,
                             'moving_average_window': moving_average_window,
                             'credentials': credentials}
            
            # Start job
            jobs_list.append(multiprocessing.Process(target=run, args=(StreamClass, stream_config, resolution)))
            jobs_list[len(jobs_list) - 1].start()
    else: # Run streams passed
        # Start the monitors sessions
        jobs_list = []
        for _, stream_id in config.items('monitors'):
            stream_id = stream_id
            stream_name = None    

            # Check if ID exist
            for stream in streams:
                if stream_id == stream['id']:
                    stream_name = stream['name']
        
            if stream_name is None:
                logger.warn("Stream ID %s doesn't exist. Skipping this one.", stream_id)
                continue
            

            logger.info("Starting stream: %s", stream_name)
            
            # Configuration to pass to stream class
            stream_config = {'id': stream_id, 
                             'name': stream_name,
                             'moving_average_window': moving_average_window,
                             'credentials': credentials}
            # Start job
            jobs_list.append(multiprocessing.Process(target=run, args=(StreamClass, stream_config, resolution)))
            jobs_list[len(jobs_list) - 1].start()