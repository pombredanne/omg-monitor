import redis
import logging
import logging.handlers
from nupic.frameworks.opf.modelfactory import ModelFactory
from nupic.data.inference_shifter import InferenceShifter
import base_model_params # file containing CLA parameters
from utils import anomaly_likelihood
from time import strftime, gmtime, sleep
import calendar
import os

logger = logging.getLogger(__name__)

class Check():
    """ A NuPIC model that saves results to Redis. """

    def __init__(self, resolution, stream):

        # Instantiate NuPIC model
        model_params = base_model_params.MODEL_PARAMS
        model_params['modelParams']['sensorParams']['encoders']['value']['resolution'] = resolution

        self.model = ModelFactory.create(model_params)

        self.model.enableInference({'predictedField': 'value'})
        
        # The shifter is used to bring the predictions to the actual time frame
        self.shifter = InferenceShifter()
        
        # The anomaly likelihood object
        self.anomalyLikelihood = anomaly_likelihood.AnomalyLikelihood()

        # Set stream source
        self.stream = stream

        # Get check id
        self.check_id = self.stream.check_id

        # Setup class variables
        self.seconds_per_request = 60
        self.db = redis.Redis("localhost")

        # Setup logging
        self.logger =  logger or logging.getLogger(__name__)
        handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/check_%d.log" % self.check_id,
                                                       maxBytes=1024*1024,
                                                       backupCount=4,
                                                      )

        handler.setFormatter(logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s'))
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def train(self):
        data = self.stream.historic_data()

        for modelInput in data:
            self._update(modelInput)

    def loop(self):
        while True:
            data = self.stream.new_data()

            for modelInput in data:
                self._update(modelInput)

    def _update(self, modelInput):
        # Pass the input to the model
        result = self.model.run(modelInput)

        # Shift results
        result = self.shifter.shift(result)

        # Save multi step predictions 
        inference = result.inferences['multiStepPredictions']

        # Take the anomaly_score
        anomaly_score = result.inferences['anomalyScore']

        # Compute the Anomaly Likelihood
        likelihood = self.anomalyLikelihood.anomalyProbability(
        modelInput['value'], anomaly_score, modelInput['time'])
               
        # Get timestamp from datetime
        timestamp = calendar.timegm(modelInput['time'].timetuple())

        self.logger.info("[%d] Processing: %s", self.check_id, strftime("%Y-%m-%d %H:%M:%S", modelInput['time'].timetuple()))
                
        if inference[1]:
            try:
                # Save in redis with key = 'results:check_id' and value = 'time, status, actual, prediction, anomaly'
                self.db.rpush('results:%d' % self.check_id, 
                              '%s,%d,%d,%.5f,%.5f' % (timestamp,
                                                         result.rawInput['value'],
                                                         result.inferences['multiStepBestPredictions'][1],
                                                         anomaly_score, 
                                                         likelihood)
                             )
            except Exception:
                self.logger.warn("[%d] Could not write results to redis.", self.check_id)