#!/usr/bin/env python

import sys
from multiprocessing import Process
import json
from monitor import monitor
from utils import pingdom # Pingdom API wrapper
import redis

# Connect to redis server
_REDIS_SERVER = redis.Redis("localhost")

# Test the redis server
try:
    response = _REDIS_SERVER.client_list()
except redis.ConnectionError:
    print "Redis server is down."
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print "Usage: start.py [username] [password] [appkey] [CHECK_ID_1] [CHECK_ID_2] ..."
        sys.exit(0)
    elif len(sys.argv) == 4:
        username = sys.argv[1]
        password = sys.argv[2]
        appkey = sys.argv[3]

        # Pingdom instance
        ping = pingdom.Pingdom(username=username, password=password, appkey=appkey)

        # Get accounts checks
        try:
            checks = ping.method('checks')
        except Exception:
            print "Could not connect to Pingdom"
            sys.exit(0)

        # get just the checks
        checks = checks['checks']

        # flush redis db and write the checks in it
        _REDIS_SERVER.flushdb()
        for check in checks:
            _REDIS_SERVER.rpush("checks", check['id'])
            _REDIS_SERVER.set("check:%s" % check['id'], check['name'])

        # threads list
        threads = []

        # # Start the Flask server
        # print "Starting Flask..."
        # sys.stdout.flush()

        # threads.append(Process(target=flask_server.app.run, args=('0.0.0.0',)))
        # threads[len(threads)-1].start()

        # Start the monitors sessions
        for check in checks:
            check_id = int(check['id'])
            check_name = check['name']
            
            print "[%s] Starting..." % check_name
            sys.stdout.flush()
            
            threads.append(Process(target=monitor.run, args=(check_id, check_name, username, password, appkey)))
            threads[len(threads)-1].start()

        for a_thread in threads:
            a_thread.join()
    else:
        username = sys.argv[1]
        password = sys.argv[2]
        appkey = sys.argv[3]

        # Pingdom instance
        ping = pingdom.Pingdom(username=username, password=password, appkey=appkey)

        # Get accounts checks
        try:
            checks = ping.method('checks')
        except Exception:
            print "Could not connect to Pingdom"
            sys.exit(0)
        
        # get just the checks
        checks = checks['checks']

        # write the checks to redis
        for check in checks:
            _REDIS_SERVER.rpush("checks", check['id'])
            _REDIS_SERVER.set("check:%s" % check['id'], check['name'])

        # threads list
        threads = []

        # # Start the Flask server
        # print "Starting Flask..."
        # sys.stdout.flush()

        # threads.append(Process(target=flask_server.app.run, args=('0.0.0.0',)))
        # threads[len(threads)-1].start()
        
        # Start the monitors sessions
        for id in sys.argv[4:]:
            check_id = int(id)
            check_name = None

            # Check if ID exist
            
            for check in checks:
                if check_id == check['id']:
                    check_name = check['name']
        
            if check_name == None:
                print "Check ID %s doesn't exist." % check_id
                print "Skipping this one."
                sys.stdout.flush()
                continue
            
            print "[%s] Starting..." % check_name
            sys.stdout.flush()
            
            threads.append(Process(target=monitor.run, args=(check_id, check_name, username, password, appkey)))
            threads[len(threads)-1].start()

        for a_thread in threads:
            a_thread.join()