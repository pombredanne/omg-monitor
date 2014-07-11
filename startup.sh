#!/bin/bash

# Create logs dir
mkdir -p $LOG_DIR

# Start redis server
redis-server > $LOG_DIR/redis.log &

# Start monitors running NuPIC
./start.py $* 2> $LOG_DIR/processes.log &

# Start Go server
cd server
./server > $LOG_DIR/martini.log