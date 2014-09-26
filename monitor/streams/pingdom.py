from utils import pingdom # Pingdom API wrapper
from datetime import datetime
from collections import deque
from base import BaseStream
import logging
import os

logger = logging.getLogger(__name__)

class PingdomStream(BaseStream):
    """ Class to provide a stream of data to NuPIC. """
    
    @property
    def value_label(self):
        return "Response time"
    
    @property
    def value_unit(self):
        return "ms"

    def __init__(self, config):
        
        super(PingdomStream, self).__init__(config)

        # Set Pingdom object
        self.ping = pingdom.Pingdom(username=config['credentials']['username'], 
                                    password=config['credentials']['password'], 
                                    appkey=config['credentials']['appkey'])

        # Default value to associate with timeouts (to have something to feed NuPIC)
        self.timeout_default = 30000

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

        # Get past resuts for stream
        results = deque()
        i = 0
        while i < 1:
            try:
                pingdomResult = self.ping.method('results/%s/' % self.id, method='GET', parameters={'limit': 1000, 'offset': i*1000})
            except Exception:
                self.logger.warn("Could not get Pingdom results.", exc_info=True)
                i = i + 1
                continue
            for result in pingdomResult['results']:
                results.appendleft(result)
            i = i + 1

        historic_data = []
        for model_input in results:
             # If dont' have response time is because it's not up, so set it to a large number
            if 'responsetime' not in model_input:
                model_input['responsetime'] = self.timeout_default

            self.history.appendleft(float(model_input['responsetime']))
            model_input['value'] = self._moving_average()

            self.servertime  = int(model_input['time'])
            model_input['time'] = datetime.utcfromtimestamp(self.servertime)

            historic_data.append(model_input)

        return historic_data

    def new_data(self):
        """ Return list of new data points since last fetching. """
        
        self.logger.info("Server time before processing results: %d", self.servertime)

        new_data = []
        try:
            pingdom_results = self.ping.method('results/%s/' % self.id, method='GET', parameters={'limit': 5})['results']
        except Exception:
            self.logger.warn("Could not get Pingdom results.", exc_info=True)
            return new_data

        # If any result contains new responses (ahead of [servetime]) process it. 
        # We check the last 5 results, so that we don't many lose data points.
        for model_input in pingdom_results[4::-1]:
            if self.servertime < int(model_input['time']):
                # Update servertime
                self.servertime  = int(model_input['time'])
                model_input['time'] = datetime.utcfromtimestamp(self.servertime)

                # If don't have response time is because it's not up, so set it to a large number
                if 'responsetime' not in model_input:
                    model_input['responsetime'] = self.timeout_default

                self.history.appendleft(float(model_input['responsetime']))
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
        # Set Pingdom object
        ping = pingdom.Pingdom(username=data['credentials']['username'], 
                               password=data['credentials']['password'], 
                               appkey=data['credentials']['appkey'])
        checks = ping.method('checks')
        result = []
        for check in checks['checks']:
            result.append({'id': str(check['id']), 'name': check['name']})
        return result