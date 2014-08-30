from utils import pingdom # Pingdom API wrapper
from collections import deque
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class Stream():
    """ Class to provide a stream of data to NuPIC. """

    def __init__(self, config):
        # Set Pingdom object
        self.ping = pingdom.Pingdom(username=config['username'], password=config['password'], appkey=config['appkey'])
        self.check_id = config['check_id']

        # Default value to associate with timeouts
        self.timeout_default = 30000

        # Time to keep watch for new values
        self.servertime = None

        # Moving average window for response time smoothing (higher means smoother)
        MAVG_WINDOW = 30

        # Deque to keep history of response time input for smoothing
        self.history = deque([0.0] * MAVG_WINDOW, maxlen=MAVG_WINDOW)

        # Setup logging
        self.logger =  logger or logging.getLogger(__name__)
        handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/stream_%d.log" % self.check_id,
                                                       maxBytes=1024*1024,
                                                       backupCount=4,
                                                      )

        handler.setFormatter(logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s'))
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def historic_data(self):
        """ Return a batch of data to be used at training """

        # Get past resuts for check
        results = deque()
        i = 0
        while i < 1:
            try:
                pingdomResult = self.ping.method('results/%d/' % self.check_id, method='GET', parameters={'limit': 1000, 'offset': i*1000})
            except Exception:
                self.logger.warn("[%d] Could not get Pingdom results.", self.check_id)
                i = i + 1
                continue
            for result in pingdomResult['results']:
                    results.appendleft(result)
            i = i + 1

        historic_data = []
        for modelInput in results:
             # If dont' have response time is because it's not up, so set it to a large number
            if 'responsetime' not in modelInput:
                modelInput['responsetime'] = self.timeout_default

            self.history.appendleft(int(modelInput['responsetime']))
            modelInput['value'] = self._moving_average()

            self.servertime  = int(modelInput['time'])
            modelInput['time'] = datetime.utcfromtimestamp(self.servertime)

            historic_data.append(modelInput)

        return historic_data

    def new_data(self):
        """ Return list of new data points since last fetching. """

        new_data = []
        try:
            pingdomResults = self.ping.method('results/%d/' % self.check_id, method='GET', parameters={'limit': 5})['results']
        except Exception, e:
            self.logger.warn("[%d][online] Could not get Pingdom results.", self.check_id, exc_info=True)
            return new_data

        # If any result contains new responses (ahead of [servetime]) process it. 
        # We check the last 5 results, so that we don't many lose data points.
        for modelInput in [pingdomResults[4], pingdomResults[3], pingdomResults[2], pingdomResults[1], pingdomResults[0]]:
            if self.servertime < int(modelInput['time']):
                # Update servertime
                self.servertime  = int(modelInput['time'])
                modelInput['time'] = datetime.utcfromtimestamp(self.servertime)

                # If don't have response time is because it's not up, so set it to a large number
                if 'responsetime' not in modelInput:
                    modelInput['responsetime'] = self.timeout_default

                self.history.appendleft(int(modelInput['responsetime']))
                modelInput['value'] = self._moving_average()

                new_data.append(modelInput)
        return new_data

    def _moving_average(self):
        """ Used to smooth input data. """

        return sum(self.history)/len(self.history) if len(self.history) > 0 else 0 