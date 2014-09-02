stream: libratocpu

credentials:
    username: USERNAME
    token: TOKEN

parameters:
    encoder_resolution: 25
    moving_average_window: 5
    seconds_per_request: 60
    likelihood_threshold: 1.0 # Optional
    anomaly_threshold: 1.0 # Optional

webhook: http://localhost/listening

worker: process # Can be: process or thread

monitors: [cw.ajsujasdjisad, cw.asdsdsadasdasd]