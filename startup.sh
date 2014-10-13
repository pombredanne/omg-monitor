#!/bin/bash

# Create logs dir
mkdir -p $LOG_DIR

# Put monitor args on env variable to be accessed by supervisor
export MONITOR_ARGS=$*

# Start monitors running NuPIC
if [ -z "$DYNAMIC" ]; then
    # If to tail
    if [ -z "$TAIL" ]; then
        exec supervisord -c /home/docker/omg-monitor/config/supervisor.conf
    else
        supervisord -c /home/docker/omg-monitor/config/supervisor.conf &
        multitail -Q 2 $LOG_DIR/*
    fi
else
    # If to tail
    if [ -z "$TAIL" ]; then
        exec supervisord -c /home/docker/omg-monitor/config/supervisor_dynamic.conf
    else
        supervisord -c /home/docker/omg-monitor/config/supervisor_dynamic.conf &
        multitail -Q 2 $LOG_DIR/*
    fi
fi
