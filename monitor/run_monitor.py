#!/usr/bin/env python

import sys
import os
import multiprocessing
from monitor import Monitor
from streams.pingdom import PingdomStream
import logging
import logging.handlers
import yaml
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
        logger.info("Usage: run_monitor.py [config1.yaml config2.yaml ...]")
        sys.exit(0)
    
    jobs_list = []
    for config_file in sys.argv[1:]:
        config = yaml.load(file(config_file, 'r'))
        
        stream_type= config['stream']

        stream_module = importlib.import_module("streams.%s" % stream_type)
        StreamClass = getattr(stream_module, "%sStream" % stream_type.title())

        # Set credentials dict
        credentials = {}
        for name, value in config['credentials'].items():
            credentials[name] = value

        try:
            streams = StreamClass.available_streams(credentials)
        except Exception, e:
            logger.error('Could not connect to stream.', exc_info=True)
            sys.exit(0)

        # Get parameters
        resolution = int(config['parameters']['encoder_resolution'])
        moving_average_window = int(config['parameters']['moving_average_window'])

        # If don't have specfied monitors, run everything!
        monitors_ids = config.get('monitors', None)
        if monitors_ids is None: 
            # Start the monitors sessions                 
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
            for stream_id in monitors_ids:
                stream_id = str(stream_id)
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

    for job in jobs_list:
        logger.info("Joining %s.", job.name)
        job.join()