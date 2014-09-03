import redis
import logging
import logging.handlers
from nupic.frameworks.opf.modelfactory import ModelFactory
from nupic.data.inference_shifter import InferenceShifter
import base_model_params # file containing CLA parameters
from utils import anomaly_likelihood
from time import strftime, sleep
from datetime import datetime
import calendar
import os
import requests

logger = logging.getLogger(__name__)

class Monitor(object):
    """ A NuPIC model that saves results to Redis. """

    def __init__(self, config):

        # Instantiate NuPIC model
        model_params = base_model_params.MODEL_PARAMS
        model_params['modelParams']['sensorParams']['encoders']['value']['resolution'] = config['resolution']

        self.model = ModelFactory.create(model_params)

        self.model.enableInference({'predictedField': 'value'})
        
        # The shifter is used to bring the predictions to the actual time frame
        self.shifter = InferenceShifter()
        
        # The anomaly likelihood object
        self.anomalyLikelihood = anomaly_likelihood.AnomalyLikelihood()

        # Set stream source
        self.stream = config['stream']

        # Setup class variables
        self.seconds_per_request = config['seconds_per_request']
        self.db = redis.Redis("localhost")

        # Set webhook
        self.webhook = config.get('webhook', None)

        # Set anomaly threshold
        self.anomaly_threshold = config.get('anomaly_threshold', None)

        # Set likelihood threshold
        self.likelihood_threshold = config.get('likelihood_threshold', None)

        # Setup logging
        self.logger =  logger or logging.getLogger(__name__)
        handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/monitor_%s.log" % self.stream.name,
                                                       maxBytes=1024*1024,
                                                       backupCount=4,
                                                      )

        handler.setFormatter(logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s'))
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Write metadata to Redis
        try:
            # Save in redis with key = 'results:monitor_id' and value = 'time, status, actual, prediction, anomaly'
            self.db.set('name:%s' % self.stream.id, self.stream.name)
            self.db.set('value_label:%s' % self.stream.id, self.stream.value_label)
            self.db.set('value_unit:%s' % self.stream.id, self.stream.value_unit)
        except Exception:
            self.logger.warn("Could not write results to redis.", exc_info=True)

    def train(self):
        data = self.stream.historic_data()

        for model_input in data:
            self._update(model_input, False) # Don't post anomalies in training

    def loop(self):
        while True:
            data = self.stream.new_data()

            for model_input in data:
                self._update(model_input, True) # Post anomalies when online

            sleep(self.seconds_per_request)

    def _update(self, model_input, is_to_post):
        # Pass the input to the model
        result = self.model.run(model_input)

        # Shift results
        result = self.shifter.shift(result)

        # Save multi step predictions 
        inference = result.inferences['multiStepPredictions']

        # Take the anomaly_score
        anomaly_score = result.inferences['anomalyScore']

        # Compute the Anomaly Likelihood
        likelihood = self.anomalyLikelihood.anomalyProbability(model_input['value'], 
                                                               anomaly_score, 
                                                               model_input['time'])
               
        # Get timestamp from datetime
        timestamp = calendar.timegm(model_input['time'].timetuple())

        self.logger.info("Processing: %s", strftime("%Y-%m-%d %H:%M:%S", model_input['time'].timetuple()))
                
        # Write and send post to webhook
        if is_to_post and self.webhook is not None:
            report = {'anomaly_score': anomaly_score, 
                      'likelihood': likelihood,
                      'model_input':  model_input}
            report['triggered_threshold'] = []
            
            # Set trigger
            if self.anomaly_threshold is not None:
                if anomaly_score > self.anomaly_threshold:
                    report['triggered_threshold'].append('anomaly_score')

            if self.likelihood_threshold is not None:
                if likelihood > self.likelihood_threshold:
                    report['triggered_threshold'].append('likelihood')

            # Post only if one of the triggered_threshold is not empty
            if report['triggered_threshold'] != []:
                self._send_post(report)

        # Save results to Redis
        if inference[1]:
            try:
                # Save in redis with key = 'results:monitor_id' and value = 'time, actual, prediction, anomaly'
                self.db.rpush('results:%s' % self.stream.id, 
                              '%s,%.5f,%.5f,%.5f,%.5f' % (timestamp,
                                                          result.rawInput['value'],
                                                          result.inferences['multiStepBestPredictions'][1],
                                                          anomaly_score, 
                                                          likelihood))
            except Exception:
                self.logger.warn("Could not write results to redis.", exc_info=True)

    def _send_post(self, report):
        """ Send HTTP POST notification. """

        payload = {}
        payload['sent_at'] = datetime.utcnow().isoformat()
        payload['report'] = report

        headers = {'Content-Type': 'application/json'}
        response = requests.post(self.webhook, data=payload, headers=headers)
            
        self.logger.info('Anomaly posted with status code %d: %s', 
                         response.status_code, response.text)