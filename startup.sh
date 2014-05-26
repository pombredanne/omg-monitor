#!/bin/bash

# Start redis server
redis-server > server/public/log/redis.log &

# Start monitors running NuPIC
./start.py $* 2> server/public/log/processes.log &

# Start Go server
cd server
./server > public/log/martini.log