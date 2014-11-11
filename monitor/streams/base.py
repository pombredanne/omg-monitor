import abc
from collections import deque

class abstractclassmethod(classmethod):
    """ Decorator for a abstract class method. """
    __isabstractmethod__ = True

    def __init__(self, callable_):
        callable_.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(callable_)

class BaseStream(object):
    """ Base class to provide a stream of data to NuPIC. """
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def  value_label(self):
        """ Label of the value being streamed.
            Examples: CPU Utilization, Response Time, Power Consumption.
        """
        pass

    @abc.abstractproperty
    def  value_unit(self):
        """ Unit of the value being streamed.
            Examples: %, ms, MW.
        """
        pass

    def __init__(self, config):
        # Get stream_id from config
        self.id = config['id']

        # Get stream name from config (default to self.id)
        self.name = config['name']

        # Time to keep watch for new values
        self.servertime = 0

        # By default, scaling_factor = 1 and moving_average_window = 1,
        # which means no transformation
        self.scaling_factor = config.get('scaling_factor', 1)
        moving_average_window = config.get('moving_average_window', 1)

        # Deque to keep history of input values for smoothing
        self.history = deque([0.0] * moving_average_window, maxlen=moving_average_window)

    @abc.abstractmethod
    def historic_data(self):
        """ Return a list of data to be used at training.
            Should return a structure like this:
                [{'raw_value': r1, 'value': v1, 'time': t1}, {'raw_value': r1, 'value': v2, 'time': t2}]
            The fields are:
            * 'raw_value': raw value for the metric.
            * 'value': averaged value (see moving_average) passed to the model.
            * 'time': unix timestamp used to compute anomaly likelihood.
        """
        pass

    @abc.abstractmethod
    def new_data(self):
        """ Return a list of new data since last update.
            Should return a structure like this:
                [{'raw_value': r1, 'value': v1, 'time': t1}, {'raw_value': r1, 'value': v2, 'time': t2}]
            The fields are:
            * 'raw_value': raw value for the metric.
            * 'value': averaged value (see moving_average) passed to the model.
            * 'time': unix timestamp used to compute anomaly likelihood.
        """
        pass

    @abstractclassmethod
    def available_streams(cls, data):
        """ Return a list with available streams for the class implementing this. Should return a list :
                [{'id': i1, 'name': n1}, {'id': i2, 'name': n2}]
        """
        pass

    def _transform(self):
        """ Used to transform data before feeding it to NuPIC. """
        # Perform average, if want
        averaged = self._moving_average()

        # Perform scaling, if want
        averaged_scaled = averaged*self.scaling_factor

        return averaged_scaled

    def _moving_average(self):
        """ Used to smooth input data. """

        return sum(self.history)/len(self.history) if len(self.history) > 0 else 0.0
