MODEL_PARAMS = {

    'aggregationInfo': 
        {   'hours': 0, 
            'microseconds': 0, 
            'seconds': 0, 
            'fields': [], 
            'weeks': 0, 
            'months': 0, 
            'minutes': 0, 
            'days': 0, 
            'milliseconds': 0, 
            'years': 0}, 

    'model': 'CLA', 
    'version': 1, 
    'predictAheadTime': None, 

    'modelParams': 
        {   'sensorParams': {
                'verbosity': 0, 
                'encoders': {
                    u'responsetime': {
                        'maxval': 600, 
                        'name': 'responsetime', 
                        'clipInput': True, 
                        'minval': 1, 
                        'n': 721, 
                        'fieldname': 'responsetime', 
                        'w': 21, 'type': 'ScalarEncoder'}
                        }, 
                'sensorAutoReset': None}, 

            'anomalyParams': {
                u'anomalyCacheRecords': None, 
                u'autoDetectThreshold': None, 
                u'autoDetectWaitRecords': None}, 

            'spParams': {
                'columnCount': 2048, 
                'spVerbosity': 0, 
                'randomSP': 1, 
                'synPermConnected': 0.1, 
                'numActivePerInhArea': 40, 
                'seed': 1956, 
                'globalInhibition': 1, 
                'inputWidth': 0, 
                'synPermInactiveDec': 0.01, 
                'synPermActiveInc': 0.1, 
                'coincInputPoolPct': 0.5}, 

            'spEnable': True, 

            'clParams': {
                'alpha': 0.01, 
                'clVerbosity': 0, 
                'steps': '1', 
                'regionName': 'CLAClassifierRegion'}, 

            'inferenceType': 'TemporalAnomaly', 
            'tpEnable': True, 
            'tpParams': {
                'columnCount': 2048, 
                'activationThreshold': 16, 
                'pamLength': 2, 
                'cellsPerColumn': 32, 
                'permanenceInc': 0.1, 
                'minThreshold': 12, 
                'verbosity': 0, 
                'maxSynapsesPerSegment': 32, 
                'outputType': 'normal', 
                'initialPerm': 0.21, 
                'globalDecay': 0.0, 
                'maxAge': 0, 
                'permanenceDec': 0.1, 
                'seed': 1960, 
                'newSynapseCount': 20, 
                'maxSegmentsPerCell': 128, 
                'temporalImp': 'cpp', 
                'inputWidth': 2048}, 

            'trainSPNetOnlyIfRequested': False
            }
        }