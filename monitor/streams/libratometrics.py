import librato
from datetime import datetime
from base import BaseStream
import logging
import os
import time

logger = logging.getLogger(__name__)

class LibratometricsStream(BaseStream):
    """ Class to provide a stream of data to NuPIC. """

    @property
    def value_label(self):
        return self._value_label

    @property
    def value_unit(self):
        return self._value_unit

    def __init__(self, config):

        super(LibratometricsStream, self).__init__(config)

        # Set Librato object
        self.libr = librato.connect(config['credentials']['username'],
                                    config['credentials']['token'])

        # Set metric to use
        self.metric = config['metric']

        # Get unit
        self._value_unit = self.libr.get(self.metric, count=1, resolution=1).attributes.get('display_units_short', 'u')
        self._value_label = self.metric

        # Setup logging
        self.logger =  logger or logging.getLogger(__name__)
        handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/stream_%s.log" % self.name,
                                                       maxBytes=1024*1024,
                                                       backupCount=4,
                                                      )

        handler.setFormatter(logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s'))
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)


    def historic_data(self):
        """ Return a batch of data to be used at training """

        time_now = int(time.time())
        time_start = time_now - 60*60*24*3
        historic_data = []
        while time_start < time_now:
            try:
                metric_results = self.libr.get(self.metric, start_time=time_start, count=100, resolution=60, source=self.id)
                measurements = metric_results.measurements[self.id]
            except Exception:
                logger.warn("Could not get Librato AWS CPU results.", exc_info=True)
                continue

            for model_input in measurements:
                if  self.servertime < model_input['measure_time']:
                    self.servertime  = model_input['measure_time']
                    model_input['time'] = datetime.utcfromtimestamp(self.servertime)

                    self.history.appendleft(float(model_input['value']))
                    model_input['raw_value'] = model_input['value']
                    model_input['value'] = self._moving_average()

                    historic_data.append(model_input)
            time_start = time_start + 100*60

        return historic_data

    def new_data(self):
        """ Return list of new data points since last fetching. """

        self.logger.info("Server time before processing results: %d", self.servertime)

        # Fetch last 5 results
        new_data = []
        try:
            cpu = self.libr.get(self.metric, count=5, resolution=60, source=self.id)
            librato_results = cpu.measurements[self.id]
        except Exception:
            self.logger.warn("Could not get Librato AWS CPU results.", exc_info=True)
            return new_data


        self.logger.info("Results fetched:")
        self.logger.info("\t%12s%12s", "time", "raw_value")
        for r in librato_results[-5::1]:
            self.logger.info("\t%12d%12.3f", r['measure_time'], r['value'])

        # If any result contains new responses (ahead of [servetime]) process it.
        # We check the last 5 results, so that we don't many lose data points.
        for model_input in librato_results[-5::1]:
            if self.servertime < model_input['measure_time']:
                self.servertime  = model_input['measure_time']
                model_input['time'] = datetime.utcfromtimestamp(self.servertime)

                self.history.appendleft(float(model_input['value']))
                model_input['raw_value'] = model_input['value']
                model_input['value'] = self._moving_average()

                new_data.append(model_input)

        self.logger.info("Server time after processing results: %d", self.servertime)
        self.logger.info("New data: %s", new_data)
        return new_data

    @classmethod
    def available_streams(cls, data):
        """ Return a list with available streams for the class implementing this. Should return a list :
                [{'value': v1, 'time': t1}, {'value': v2, 'time': t2}]
        """

        # Get CPU measutements (we use it get the ID of the instances)
        libr = librato.connect(data['credentials']['username'], data['credentials']['token'])

        metric = libr.get(data['metric'], count=100, resolution=1)
        instances_list = [i for i in metric.measurements]

        result = []
        for id_ in instances_list:
            result.append({'id': id_, 'name': id_}) # Doesn't have a way to get better names

        return result
