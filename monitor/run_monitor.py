#!/usr/bin/env python

import sys
import os
import multiprocessing
from monitor import Monitor
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

def validate(config):
    """ Validate configuration file. 
        Input: dict already parsed with yaml.load.
        Output: string with success or error message.
    """

    message = ''
    keys = config.keys()
    if 'stream' not in keys:
        message = message + 'Stream not specfied.\n'
    
    if 'credentials' not in keys:
        message = message + 'Credentials not specfied.\n'

    if 'parameters' not in keys:
        message = message + 'Parameters not specfied.\n'
    else:
        if 'moving_average_window' not in config['parameters'].keys():
            message = message + 'Moving average window not specfied.\n'
        elif not isinstance(config['parameters']['moving_average_window'], (int, long)):
            message = message + 'Moving average window should be an integer.\n'

        if 'encoder_resolution' not in config['parameters'].keys():
            message = message + 'Encoder resolution not specfied.\n'
        elif not isinstance(config['parameters']['encoder_resolution'], (int, long)):
            message = message + 'Encoder resolution should be an integer.\n'

        if 'seconds_per_request' not in config['parameters'].keys():
            message = message + 'Seconds per request not specfied.\n'
        elif not isinstance(config['parameters']['seconds_per_request'], (int, long)):
            message = message + 'Seconds per request should be an integer.\n'

    if 'monitors' in keys:
        if not isinstance(config['monitors'], list):
            message = message + 'Monitors should be a list of ids.\n'

    return message

def run(stream_config, monitor_config):
    """ Instantiate a monitor for StreamClass using given configurations """

    # Instantiate monitor
    logger.info("Stantiating monitor: %s", stream_config['name'])

    # Instantiate stream
    stream = StreamClass(stream_config)

    # Add stream to monitor configuration
    monitor_config['stream'] = stream

    # Instantiate monitor
    monitor = Monitor(monitor_config)

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
        # Parse YAML configuration file
        try:
            config = yaml.load(file(config_file, 'r'))
        except Exception:
            logger.error('Invalid configuration file: %s', config_file, exc_info=True)
            continue
 
        # Validade configuration
        validation_message = validate(config)
        if validation_message != '':
            logger.error('Invalid configuration file: %s\n%s', config_file, validation_message)
            continue
        logger.info('Configuration file validated.')

        # Get stream type and set StreamClass from it
        stream_type= config['stream']

        stream_module = importlib.import_module("streams.%s" % stream_type)
        StreamClass = getattr(stream_module, "%sStream" % stream_type.title())

        # Set credentials dict
        credentials = {}
        for name, value in config['credentials'].items():
            credentials[name] = value

        # Get all streams available for StreamClass
        try:
            streams = StreamClass.available_streams(credentials)
        except Exception, e:
            logger.error('Could not connect to stream.', exc_info=True)
            sys.exit(0)

        # Get configurations to pass to monitor class
        monitor_config = {'resolution': int(config['parameters']['encoder_resolution']),
                          'seconds_per_request': int(config['parameters']['seconds_per_request']),
                          'webhook': config.get('webhook', None),
                          'anomaly_threshold': config.get('anomaly_threshold', None),
                          'likelihood_threshold': config.get('likelihood_threshold', None)}

        # Get other stream parameters
        moving_average_window = int(config['parameters']['moving_average_window'])

        # If don't have specfied monitors, run everything!
        monitors_ids = config.get('monitors', None)
        if monitors_ids is None:
            logger.info('No monitors IDs in configuration file. Will run everything.')

            # Start the monitors sessions                 
            for stream in streams:
                stream_id = stream['id']
                stream_name = stream['name']
                
                # Configuration to pass to stream class
                stream_config = {'id': stream_id, 
                                 'name': stream_name,
                                 'moving_average_window': moving_average_window,
                                 'credentials': credentials}
                
                # Start job
                jobs_list.append(multiprocessing.Process(target=run, args=(stream_config, monitor_config)))
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
                
                # Configuration to pass to stream class
                stream_config = {'id': stream_id, 
                                 'name': stream_name,
                                 'moving_average_window': moving_average_window,
                                 'credentials': credentials}
                
                # Start job
                jobs_list.append(multiprocessing.Process(target=run, args=(stream_config, monitor_config)))
                jobs_list[len(jobs_list) - 1].start()
    # Join jobs
    for job in jobs_list:
        logger.info("Joining job %s.", job.name)
        job.join()