#!/usr/bin/env python

import sys
from check import Check
from stream import Stream
import logging


logging.basicConfig() 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def run(stream_config, resolution):
    # Instantiate check
    logger.info("Stantiating check.")

    stream = Stream(stream_config)
    check = Check(resolution, stream)

    # Train check
    logger.info("Starting training.")  
    check.train()
        
    # Enter loop for online learning
    logger.info("Going online.")  
    check.loop()    

if __name__ == "__main__":
    if(len(sys.argv) <= 4 or len(sys.argv) >= 6):
        logger.info("Usage: run_check.py [username] [password] [appkey] [CHECK_ID]")
        sys.exit(0)

    # If 4 arguments is passed, everything is alright
    if(len(sys.argv) == 5):
        username = sys.argv[1]
        password = sys.argv[2]
        appkey = sys.argv[3]
        check_id = int(sys.argv[4])

        stream_config = {'username': username, 'password': password, 'appkey': appkey, 'check_id': check_id}
        encoder_resolution = 25
        run(stream_config, encoder_resolution)