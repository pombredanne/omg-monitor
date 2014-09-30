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
import json

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
        self.db = redis.Redis('localhost')
        self.seconds_per_request = config['seconds_per_request']
        self.webhook = config['webhook']
        self.anomaly_threshold = config['anomaly_threshold']
        self.likelihood_threshold = config['likelihood_threshold']

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

        self.logger.info("=== Settings ===")
        self.logger.info("Webhook: %s", self.webhook)
        self.logger.info("Anomaly threshold: %.2f", self.anomaly_threshold)
        self.logger.info("Likelihood: %.2f", self.likelihood_threshold)
        self.logger.info("Seconds per request: %d", self.seconds_per_request)

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
                      'model_input': {'time': model_input['time'].isoformat(),
                                      'value': model_input['value']}}
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

        anomalous = False
        if self.anomaly_threshold is not None:
            if anomaly_score > self.anomaly_threshold:
              anomalous = True
        if self.likelihood_threshold is not None:
            if likelihood > self.likelihood_threshold:
              anomalous = True
        return anomalous

    def delete(self):
      """ Remove this monitor from redis """

      self.db.delete("results:%s" % self.stream.id)
      self.db.delete('name:%s' % self.stream.id)
      self.db.delete('value_label:%s' % self.stream.id)
      self.db.delete('value_unit:%s' % self.stream.id)

    def _send_post(self, report):
        """ Send HTTP POST notification. """

        payload = {}
        payload['sent_at'] = datetime.utcnow().isoformat()
        payload['report'] = report
        payload['monitor'] = self.stream.name
        payload['source'] = type(self.stream).__name__
        payload['metric'] = self.stream.value_label

        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(self.webhook, data=json.dumps(payload), headers=headers)
        except Exception:
            self.logger.warn('Failed to post anomaly.', exc_info=True)
            return

        self.logger.info('Anomaly posted with status code %d.', response.status_code)
        return
