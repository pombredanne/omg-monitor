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
    else:
        if 'source' not in config['stream'].keys():
            message = message + 'Stream source not specfied.\n'

    if 'credentials' not in keys:
        message = message + 'Credentials not specfied.\n'

    if 'parameters' in keys:
        if 'encoder_resolution' in config['parameters'].keys():
            if not isinstance(config['parameters']['encoder_resolution'], (int, long)):
                message = message + 'Encoder resolution should be an integer.\n'
        if 'seconds_per_request' in config['parameters'].keys():
            if not isinstance(config['parameters']['seconds_per_request'], (int, long)):
                message = message + 'Seconds per request should be an integer.\n'
        if 'moving_average_window' in config['parameters'].keys():
            if not isinstance(config['parameters']['moving_average_window'], (int, long)):
                message = message + 'Moving average window should be an integer.\n'
        if 'scaling_factor' in config['parameters'].keys():
            if not isinstance(config['parameters']['scaling_factor'], (float, int, long)):
                message = message + 'Scaling factor window should be a number.\n'
        if 'likelihood_threshold' in config['parameters'].keys():
            if not isinstance(config['parameters']['likelihood_threshold'], (float, int, long)):
                message = message + 'Likelihood threshold should be a number between 0 and 1.\n'
            elif config['parameters']['likelihood_threshold'] < 0 or config['parameters']['likelihood_threshold'] > 1:
                message = message + 'Likelihood threshold should be a number between 0 and 1.\n'
        if 'anomaly_threshold' in config['parameters'].keys():
            if not isinstance(config['parameters']['anomaly_threshold'], (float, int, long)):
                message = message + 'Anomaly threshold should be a number between 0 and 1.\n'
            elif config['parameters']['anomaly_threshold'] < 0 or config['parameters']['likelihood_threshold'] > 1:
                message = message + 'Anomaly threshold should be a number between 0 and 1.\n'
    if 'monitors' in keys:
        if not isinstance(config['monitors'], list):
            message = message + 'Monitors should be a list of ids.\n'

    return message

def extract_monitor_config(config):
    """ Extract Monitor config from global config file.
        Output: * monitor_config: dictionary with Monitor configurations
    """
    if 'parameters' not in config.keys():
        config['parameters'] = {}

    # Get configurations to pass to monitor class
    monitor_config = {'resolution': int(config['parameters'].get('encoder_resolution', 1)),
                      'seconds_per_request': int(config['parameters'].get('seconds_per_request', 60)),
                      'webhook': config.get('webhook', None),
                      'anomaly_threshold': config['parameters'].get('anomaly_threshold', None),
                      'likelihood_threshold': config['parameters'].get('likelihood_threshold', None),
                      'domain': config.get('domain', 'localhost'),
                      'nupic_model_params': config.get('nupic_model_params', {})}
    return monitor_config

def extract_stream_config(config):
    """ Extract Stream config from global config file. Also checks for Stream
    availability.
        Output: * stream_config: dictionary with Stream configurations
                * streams: list of available streams
                * StreamClass: stream class being used
    """
    if 'parameters' not in config.keys():
        config['parameters'] = {}
    # Set credentials dict
    credentials = {}
    for name, value in config['credentials'].items():
        credentials[name] = value

    # Get stream type and set StreamClass from it
    stream_type= config['stream']['source']

    stream_module = importlib.import_module("streams.%s" % stream_type)
    StreamClass = getattr(stream_module, "%sStream" % stream_type.title())

    # Set metric
    metric = config['stream'].get('metric', None)

    # Get all streams available for StreamClass
    data = {'credentials': credentials, 'metric': metric}
    try:
        streams = StreamClass.available_streams(data)
    except Exception:
        logger.error('Could not connect to stream.', exc_info=True)
        sys.exit(0)

    # Get base stream configurations
    stream_config = {'metric': metric,
                     'moving_average_window': int(config['parameters'].get('moving_average_window', 1)),
                     'scaling_factor': float(config['parameters'].get('scaling_factor', 1)),
                     'credentials': credentials}
    return stream_config, streams, StreamClass

def run(StreamClass, stream_config, monitor_config):
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

        # Get configurations to pass to monitor class
        monitor_config = extract_monitor_config(config)
        stream_config, streams, StreamClass = extract_stream_config(config)

        logger.info("Monitor configuration: %s", monitor_config)
        logger.info("Base stream configuration: % s", stream_config)

        # If don't have specfied monitors, run everything!
        monitors_ids = config.get('monitors', None)
        if monitors_ids is None:
            logger.info('No monitors IDs in configuration file. Will run everything.')

            # Start the monitors sessions
            for stream in streams:
                stream_id = stream['id']
                stream_name = stream['name']

                # Set stream identification
                stream_config['id'] = stream_id
                stream_config['name'] = stream_name

                # Start job
                jobs_list.append(multiprocessing.Process(target=run, args=(StreamClass, stream_config, monitor_config)))
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

                # Set stream identification
                stream_config['id'] = stream_id
                stream_config['name'] = stream_name

                # Start job
                jobs_list.append(multiprocessing.Process(target=run, args=(StreamClass, stream_config, monitor_config)))
                jobs_list[len(jobs_list) - 1].start()
    # Join jobs
    for job in jobs_list:
        logger.info("Joining job %s.", job.name)
        job.join()
