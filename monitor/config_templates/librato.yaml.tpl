# Stream configurations
stream:
  # Which stream to use
  source: libratometrics

  # Which metric to use
  # Can be, in principle, any Librato metric
  metric: AWS.EC2.CPUUTILIZATION

# Librato credentials
credentials:
    username: USERNAME
    token: TOKEN

# [Optional] Monitors parameters. Have defaults if we omit it, as shown below.
parameters:
    # Resolution of NuPIC RandomDistributedScalarEncoder to use
    encoder_resolution: 1

    # Time sleep between requests when it's in online learning
    seconds_per_request: 60

    # How many points to use for data smoothing when doing averaging
    moving_average_window: 1

    # Factor to multiply each data value when using scale transform
    scaling_factor: 1

    # Thresholds that triggers a POST to the webhook (if supplied)
    likelihood_threshold: None
    anomaly_threshold: None

# [Optional] You can override modelParams of NuPIC here. Only do that if you know
# what you're doing! Below we have some examples (notice NuPIC uses camelCase):
nupic_model_params:
    spParams:
        maxBoost: 2.0
    tpParams:
        activationThreshold: 16

# [Optional ] Domain and protocol in which you'll be running the service.
# This will be used to create links to anomalous monitors when reporting anomalies.
# If not specified we'll use "localhost" as domain and "http" as protocol.
domain: omg-monitor.ai
protocol: http

# [Optional]  An endpoint that will receive POST request when something above
# the defined thresholds is found. We post a JSON with the following structure:
#
#{
#    "sent_at": "2014-09-04T14:42:18.560047",
#    "monitor": "instance_id",
#    "source": "LibratometricsStream",
#    "metric": "AWS.EC2.CPUUTILIZATION",
#    "report": {
#        "status": "Leaving anomalous state"
#        "anomaly_score": 1,
#        "likelihood": 0.841344746,
#        "model_input": {
#            "time": "2014-09-04T14:41:26",
#            "value": 716
#        }
#    }
#}
webhook: http://localhost/listening

# [Optional] A list with instances names to monitor. If not supplied, we run everything.
monitors: [cw.ajsujasdjisad, cw.asdsdsadasdasd]
