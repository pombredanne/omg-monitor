stream: pingdom

credentials:
    username: USERNAME
    password: PASSWORD
    appkey: APPKEY

parameters:
    moving_average_window: 30
    encoder_resolution: 25
    seconds_per_request: 60

worker: process #can be process or thread

monitors: [123456, 875642]