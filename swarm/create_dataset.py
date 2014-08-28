#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------

"""A simple client to create a CLA model for Monitor."""

from datetime import datetime
from collections import deque
import sys
import csv
from time import strftime, gmtime, sleep

from utils import pingdom # Pingdom API wrapper

_UTC_OFFSET = 10800 # Time zone offset (-3:00 GMT for Sao Paulo/Brazil)
_TIMEOUT = 60000 # Default response time when status is not 'up' (ms)
_SECONDS_PER_REQUEST = 60 # Sleep time between requests (in seconds)

def create_dataset(check_id, username, password, appkey):
    # Pingdom instance
    ping = pingdom.Pingdom(username=username, password=password, appkey=appkey)


    print "[%s] Getting last 5000 results" % check_id
    sys.stdout.flush()

    # Get past resuts for check
    results = deque()
    i = 0
    while i < 6:
        try:
            pingdomResult = ping.method('results/%d/' % check_id, method='GET', parameters={'limit': 1000, 'offset': i*1000})
        except Exception, e:
            print "[%s] Could not get Pingdom results." % check_id
            print e
            sleep(_SECONDS_PER_REQUEST)
            continue
        for result in pingdomResult['results']:
            results.appendleft(result)
        i = i + 1

    servertime = None
    with open('swarm/dataset.csv', 'wb') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(['time', 'status', 'responsetime'])
        writer.writerow(['datetime', 'string', 'float'])
        writer.writerow(['T', '', ''])
        for modelInput in results:
            # If dont' have response time is because it's not up, so set it to a large number
            if 'responsetime' not in modelInput:
                modelInput['responsetime'] = _TIMEOUT

            modelInput['responsetime'] = int(modelInput['responsetime'])
            servertime  = int(modelInput['time'])
            modelInput['time'] = datetime.utcfromtimestamp(servertime)

            print("[%s] Processing: %s") % (check_id, strftime("%Y-%m-%d %H:%M:%S", gmtime(servertime - _UTC_OFFSET)))
            sys.stdout.flush()

            writer.writerow([strftime("%Y-%m-%d %H:%M:%S", gmtime(servertime)), modelInput['status'], modelInput['responsetime']])

        # while True:
        #     # Call Pingdom for the last 5 results for check_id
        #     try:
        #         pingdomResults = ping.method('results/%d/' % check_id, method='GET', parameters={'limit': 5})['results']
        #     except Exception, e:
        #         print "[%s][online] Could not get Pingdom results." % check_id
        #         print e
        #         sleep(_SECONDS_PER_REQUEST)
        #         continue
            
        #     # If any result contains new responses (ahead of [servetime]) process it. 
        #     # We check the last 5 results, so that we don't many lose data points.
        #     for modelInput in [pingdomResults[4], pingdomResults[3], pingdomResults[2], pingdomResults[1], pingdomResults[0]]:
        #         if servertime < int(modelInput['time']):
        #             # Update servertime
        #             servertime  = int(modelInput['time'])
        #             modelInput['time'] = datetime.utcfromtimestamp(servertime)

        #             # If not have response time is because it's not up, so set it to a large number
        #             if 'responsetime' not in modelInput:
        #                 modelInput['responsetime'] = _TIMEOUT

        #             modelInput['responsetime'] = int(modelInput['responsetime'])

        #             print("[%s][online] Processing: %s") % (check_id, strftime("%Y-%m-%d %H:%M:%S", gmtime(servertime - _UTC_OFFSET)))
        #             sys.stdout.flush()

        #             writer.writerow([servertime, modelInput['status'], modelInput['responsetime']])

        #     # Wait until next request
        #     sleep(_SECONDS_PER_REQUEST)

if __name__ == "__main__":
    if(len(sys.argv) <= 4):
        print "Usage: create_dataset.py [username] [password] [appkey] [CHECK_ID]"
        sys.exit(0)

    # If 4 arguments passed, set check_id
    if(len(sys.argv) == 5):
        username = sys.argv[1]
        password = sys.argv[2]
        appkey = sys.argv[3]
        check_id = int(sys.argv[4])

    # Create dataset
    create_dataset(check_id, username, password, appkey)