import redis
import logging
import logging.handlers
from nupic.frameworks.opf.modelfactory import ModelFactory
from nupic.data.inference_shifter import InferenceShifter
import base_model_params # file containing CLA parameters
from nupic.algorithms.anomaly_likelihood import AnomalyLikelihood
from time import strftime, sleep
from datetime import datetime
import calendar
import os
import requests
import json
import collections

def update_dict(d, u):
    """ Recursively updates dict d with keys in dict u."""
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = update_dict(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d

logger = logging.getLogger(__name__)

class Monitor(object):
    """ A NuPIC model that saves results to Redis. """

    def __init__(self, config):

        # Instantiate NuPIC model
        model_params = base_model_params.MODEL_PARAMS

        # Set resolution
        model_params['modelParams']['sensorParams']['encoders']['value']['resolution'] = config['resolution']

        # Override other Nupic parameters:
        model_params['modelParams'] = update_dict(model_params['modelParams'], config['nupic_model_params'])

        # Create model and enable inference on it
        self.model = ModelFactory.create(model_params)
        self.model.enableInference({'predictedField': 'value'})

        # The shifter is used to bring the predictions to the actual time frame
        self.shifter = InferenceShifter()

        # The anomaly likelihood object
        self.anomalyLikelihood = AnomalyLikelihood()

        # Set stream source
        self.stream = config['stream']

        # Setup class variables
        self.db = redis.Redis('localhost')
        self.seconds_per_request = config['seconds_per_request']
        self.webhook = config['webhook']
        self.channel = config['channel']
        self.anomaly_threshold = config['anomaly_threshold']
        self.likelihood_threshold = config['likelihood_threshold']
        self.domain = config['domain']
        self.protocol = config['protocol']
        self.alert = False # Toogle when we get above threshold

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
        self.logger.info("Channel: %s", self.channel)
        self.logger.info("Domain: %s", self.domain)
        self.logger.info("Seconds per request: %d", self.seconds_per_request)
        self.logger.info("Model params: %s", model_params)

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
            self.update(model_input, False) # Don't post anomalies in training

    def loop(self):
        while True:
            data = self.stream.new_data()

            for model_input in data:
                self.update(model_input, True) # Post anomalies when online

            sleep(self.seconds_per_request)

    def update(self, model_input, is_to_post):
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

        # Get the predicted value for reporting
        predicted = result.inferences['multiStepBestPredictions'][1]

        # Get timestamp from datetime
        timestamp = calendar.timegm(model_input['time'].timetuple())

        self.logger.info("Processing: %s", strftime("%Y-%m-%d %H:%M:%S", model_input['time'].timetuple()))

        # Save results to Redis
        if inference[1]:
            try:
                # Save in redis with key = 'results:monitor_id' and value = 'time, raw_value, actual, prediction, anomaly'
                # * actual: is the value processed  by the NuPIC model, which can be
                #           an average of raw_values
                # * predicition: prediction based on 'actual' values.
                self.db.rpush('results:%s' % self.stream.id,
                              '%s,%.5f,%.5f,%.5f,%.5f,%.5f' % (timestamp,
                                                          model_input['raw_value'],
                                                          result.rawInput['value'],
                                                          predicted,
                                                          anomaly_score,
                                                          likelihood))
                max_items = 10000
                ln = self.db.llen('results:%s' % self.stream.id)
                if ln > max_items:
                    self.db.ltrim('results:%s' % self.stream.id, ln - max_items, ln)
            except Exception:
                self.logger.warn("Could not write results to redis.", exc_info=True)

        # See if above threshold (in which case anomalous is True)
        anomalous = False
        if self.anomaly_threshold is not None:
            if anomaly_score >= self.anomaly_threshold:
                anomalous = True
        if self.likelihood_threshold is not None:
            if likelihood >= self.likelihood_threshold:
                anomalous = True

        # Post if webhook is not None
        if is_to_post and self.webhook is not None:
            # Check if it was in alert state in previous time step
            was_alerted = self.alert
            # Update alert state
            self.alert = anomalous

            # Send notification if webhook is set and if:
            # was not alerted before and is alerted now (entered anomalous state)
            # or
            # was alerted before and is not alerted now (left anomalous state)
            if not was_alerted and self.alert:
                report = {'anomaly_score': anomaly_score,
                          'likelihood': likelihood,
                          'model_input': {'time': model_input['time'].isoformat(),
                                          'value': model_input['raw_value']}}
                self._send_post(report)

        # Return anomalous state
        return {"likelihood" : likelihood,  "anomalous" : anomalous, "anomalyScore" : anomaly_score, "predicted" : predicted}

    def delete(self):
        """ Remove this monitor from redis """

        self.db.delete("results:%s" % self.stream.id)
        self.db.delete('name:%s' % self.stream.id)
        self.db.delete('value_label:%s' % self.stream.id)
        self.db.delete('value_unit:%s' % self.stream.id)

    def _send_post(self, report):
        """ Send HTTP POST notification. """

        chart_url = '%s://%s?id=%s' % (self.protocol, self.domain, self.stream.id)
        if os.getenv('SERVER_TOKEN') != '':
            chart_url += '&access_token=%s' % os.getenv('SERVER_TOKEN')

        if "hooks.slack.com" not in self.webhook:
            payload = {'sent_at': datetime.utcnow().isoformat(),
                       'report': report,
                       'monitor': self.stream.name,
                       'source': type(self.stream).__name__,
                       'metric': '%s (%s)' % (self.stream.value_label, self.stream.value_unit),
                       'chart': chart_url}
        else:
            payload = {'username': 'omg-monitor',
                       'icon_url': 'https://rawgithub.com/cloudwalkio/omg-monitor/slack-integration/docs/images/post_icon.png',
                       'text':  'Anomalous state in *%s* from _%s_:' % (self.stream.name, type(self.stream).__name__),
                       'attachments': [{'color': 'warning',
                                        'fields': [{'title': 'Chart',
                                                    'value':  chart_url,
                                                    'short': False},
                                                   {'title': 'Metric',
                                                    'value': self.stream.value_label,
                                                    'short': True},
                                                   {'title': 'Value',
                                                    'value': str(report['model_input']['value']) + ' ' + self.stream.value_unit,
                                                    'short': True}]}]}
            if self.channel is not None:
                payload['channel'] = self.channel

        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(self.webhook, data=json.dumps(payload), headers=headers)
        except Exception:
            self.logger.warn('Failed to post anomaly.', exc_info=True)
            return

        self.logger.info('Anomaly posted with status code %d: %s', response.status_code, response.text)
        return
