#!/bin/bash

# Create logs dir
mkdir -p $LOG_DIR

# Start redis server
redis-server > $LOG_DIR/redis.log &

# Start monitors running NuPIC
if [ -z "$DYNAMIC" ]; then
	./monitor/run_monitor.py $* 2> $LOG_DIR/processes.log &
else
	./monitor/run_monitor_dyn.py $* 2> $LOG_DIR/processes.log &
fi



# Start Go server
cd server
if [ -z "$TAIL" ]; then
	exec ./server > $LOG_DIR/martini.log
else
	./server > $LOG_DIR/martini.log &
	tail -F $LOG_DIR/*
fi
