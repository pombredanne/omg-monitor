#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------

"""A simple client to create a CLA model for Monitor."""

from datetime import datetime
from collections import deque
import os
import sys
import thread
import logging
import logging.handlers
from time import strftime, gmtime, sleep

from nupic.frameworks.opf.modelfactory import ModelFactory
from nupic.data.inference_shifter import InferenceShifter
import model_params_monitor # file containing CLA parameters

import redis
from utils import pingdom # Pingdom API wrapper
from utils import anomaly_likelihood

_TIMEOUT = 30000 # Default response time when status is not 'up' (ms)
_SECONDS_PER_REQUEST = 60 # Sleep time between requests (in seconds)

# Connect to redis server
_REDIS_SERVER = redis.Redis("localhost")

# Top logger (for redis). Will use only when stand-alone.
logger = logging.getLogger(__name__)

# Test the redis server
try:
    response = _REDIS_SERVER.client_list()
except redis.ConnectionError:
    logger.error("Redis server is down.")
    sys.exit(0)

def moving_average(data):
    """ Used to eventually smooth input data. Not used now. """
    return sum(data)/len(data) if len(data) > 0 else 0 

def create_model():
    """ Create the CLA model """
    return ModelFactory.create(model_params_monitor.MODEL_PARAMS)

def run(check_id, check_name, username, password, appkey):
    """ Main loop, responsible for initial and online training """

    # Setup logging
    logger = logging.getLogger(__name__)
    handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/monitor_%s.log" % check_name,
                                                   maxBytes=1024*1024,
                                                   backupCount=4,
                                                  )

    formatter = logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Pingdom instance
    ping = pingdom.Pingdom(username=username, password=password, appkey=appkey)

    # The shifter is used to bring the predictions to the actual time frame
    shifter = InferenceShifter()
    
    # The anomaly likelihood object
    anomalyLikelihood = anomaly_likelihood.AnomalyLikelihood()

    model = create_model() # Create the CLA model

    model.enableInference({'predictedField': 'responsetime'})

    # Moving average window for response time smoothing (higher means smoother)
    MAVG_WINDOW = 30

    # Deque to keep history of response time input for smoothing
    history = deque([0.0] * MAVG_WINDOW, maxlen=MAVG_WINDOW)

    logger.info("[%s] Getting last 5000 results", check_name)
    
    # Get past resuts for check
    results = deque()
    i = 0
    while i < 6:
        try:
            pingdomResult = ping.method('results/%d/' % check_id, method='GET', parameters={'limit': 1000, 'offset': i*1000})
        except Exception:
            logger.warn("[%s] Could not get Pingdom results.", check_name)
            continue
        for result in pingdomResult['results']:
            results.appendleft(result)
        i = i + 1

    servertime = None 
    for modelInput in results:
        # If dont' have response time is because it's not up, so set it to a large number
        if 'responsetime' not in modelInput:
            modelInput['responsetime'] = _TIMEOUT

        history.appendleft(int(modelInput['responsetime']))
        modelInput['responsetime'] = moving_average(history)

        servertime  = int(modelInput['time'])
        modelInput['time'] = datetime.utcfromtimestamp(servertime)

        # Pass the input to the model
        result = model.run(modelInput)
        # Shift results
        result = shifter.shift(result)
        # Save multi step predictions 
        inference = result.inferences['multiStepPredictions']
        # Take the anomaly_score
        anomaly_score = result.inferences['anomalyScore']
        # Compute the Anomaly Likelihood
        likelihood = anomalyLikelihood.anomalyProbability(
            modelInput['responsetime'], anomaly_score, modelInput['time'])
       
        logger.info("[%s] Processing: %s", check_name, strftime("%Y-%m-%d %H:%M:%S", gmtime(servertime)))
    
        if inference[1]:
            try:
                # Save in redis with key = 'results:check_id' and value = 'time, status, actual, prediction, anomaly'
                _REDIS_SERVER.rpush('results:%d' % check_id, 
                                    '%s,%s,%d,%d,%.5f,%.5f' % (servertime,
                                                               modelInput['status'],
                                                               result.rawInput['responsetime'],
                                                               result.inferences['multiStepBestPredictions'][1],
                                                               anomaly_score, 
                                                               likelihood)
                                                              )
            except Exception:
                logger.warn("[%s] Could not write results to redis.", check_name)
                continue

    logger.info("[%s] Let's start learning online...", check_name)

    # Main loop
    try:  
        while True:
            # Call Pingdom for the last 5 results for check_id
            try:
                pingdomResults = ping.method('results/%d/' % check_id, method='GET', parameters={'limit': 5})['results']
            except Exception:
                logger.warn("[%s][online] Could not get Pingdom results.", check_name, exc_info=True)
                sleep(_SECONDS_PER_REQUEST)
                continue
            
            # If any result contains new responses (ahead of [servetime]) process it. 
            # We check the last 5 results, so that we don't many lose data points.
            for modelInput in [pingdomResults[4], pingdomResults[3], pingdomResults[2], pingdomResults[1], pingdomResults[0]]:
                if servertime < int(modelInput['time']):
                    # Update servertime
                    servertime  = int(modelInput['time'])
                    modelInput['time'] = datetime.utcfromtimestamp(servertime)

                    # If not have response time is because it's not up, so set it to a large number
                    if 'responsetime' not in modelInput:
                        modelInput['responsetime'] = _TIMEOUT

                    history.appendleft(int(modelInput['responsetime']))
                    modelInput['responsetime'] = moving_average(history)

                    # Pass the input to the model
                    result = model.run(modelInput)
                    # Shift results
                    result = shifter.shift(result)
                    # Save multi step predictions 
                    inference = result.inferences['multiStepPredictions']
                    # Take the anomaly_score
                    anomaly_score = result.inferences['anomalyScore']
                    # Compute the Anomaly Likelihood
                    likelihood = anomalyLikelihood.anomalyProbability(
                        modelInput['responsetime'], anomaly_score, modelInput['time'])
                    
                    logger.info("[%s][online] Processing: %s", check_name, strftime("%Y-%m-%d %H:%M:%S", gmtime(servertime)))

                    if inference[1]:
                        try:
                            # Save in redis with key = 'results:check_id' and value = 'time, status, actual, prediction, anomaly'
                            _REDIS_SERVER.rpush('results:%d' % check_id, 
                                                '%s,%s,%d,%d,%.5f,%.5f' % (servertime,
                                                                           modelInput['status'],
                                                                           result.rawInput['responsetime'],
                                                                           result.inferences['multiStepBestPredictions'][1],
                                                                           anomaly_score, 
                                                                           likelihood)
                                                                          )
                        except Exception:
                            logger.warn("[%s] Could not write results to redis.", check_name, exc_info=True)
                            continue
                    else:
                        logger.warn("[%s] Don't have inference[1]: %s.", check_name, inference)

            # Wait until next request
            sleep(_SECONDS_PER_REQUEST)
    except Exception:
        logger.warn("[%s] Out of main loop.", check_name, exc_info=True)
        sys.exit(0)

if __name__ == "__main__":
    if(len(sys.argv) <= 4):
        print "Usage: monitor.py [username] [password] [appkey] [CHECK_ID]"
        sys.exit(0)

    # If 4 arguments passed, set check_id
    if(len(sys.argv) == 5):
        username = sys.argv[1]
        password = sys.argv[2]
        appkey = sys.argv[3]
        check_id = int(sys.argv[4])
        check_name = str(check_id)

    # If 5 argumentw passed, set check_id and check_name
    if(len(sys.argv) == 6):
        username = sys.argv[1]
        password = sys.argv[2]
        appkey = sys.argv[3]
        check_id = int(sys.argv[4])
        check_name = sys.argv[5]
    
    # Run the monitor
    run(check_id, check_name, username, password, appkey)