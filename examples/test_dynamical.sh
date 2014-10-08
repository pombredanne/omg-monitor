#!/bin/bash

# This is a test for pushing data in dynamically

series1() {

curl --data '{"check_id": "mic2", "time":12420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic2", "time":13420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic2", "time":14420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic2", "time":15420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic2", "time":16420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic2", "time":17420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic2", "time":18420, "value":42}' http://boot2docker:8080

}

series2() {

curl --data '{"check_id": "mic3", "time":12420, "value":42, "config": {"name": "yeah"}}' http://boot2docker:8080
curl --data '{"check_id": "mic3", "time":13420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic3", "time":14420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic3", "time":15420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic3", "time":16420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic3", "time":17420, "value":42}' http://boot2docker:8080
curl --data '{"check_id": "mic3", "time":18420, "value":42}' http://boot2docker:8080
}

series1
series2

# to delete a check (to save memory - less CLA memory and redis is cleared):
# curl -X DELETE --data '{"check_id": "mic3", "time":12420, "value":42}' http://boot2docker:8080
#
