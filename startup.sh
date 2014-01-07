#!/bin/bash

# Start redis server
redis-server > server/public/log/redis &

# Start monitors running NuPIC
./start.py $* > server/public/log/monitor &

# Start Go server
cd server
./server > public/log/martini