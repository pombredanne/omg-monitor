stream: pingdom

credentials:
    username: USERNAME
    password: PASSWORD
    appkey: APPKEY

parameters:
    moving_average_window: 30
    encoder_resolution: 25
    seconds_per_request: 60
    likelihood_threshold: 1.0 # Optional
    anomaly_threshold: 1.0 # Optional

webhook: http://localhost/listening

monitors: [123456, 875642]