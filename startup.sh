#!/bin/bash

# Create logs dir
mkdir -p $LOG_DIR

# Initialize access token to empty string
SERVER_TOKEN=

# Parse access token to SERVER_TOKEN variable
OPTIND=1
while getopts ":t:" opt; do
  case $opt in
    t)
      SERVER_TOKEN=$OPTARG
      echo "-t was triggered, Parameter: $SERVER_TOKEN" >&2
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done

# Shift parameters to get config files
shift $(expr $OPTIND - 1 )

# Put monitor args on env variable to be accessed by supervisor
export MONITOR_ARGS=$*
export SERVER_TOKEN=$SERVER_TOKEN
# Start monitors running NuPIC
if [ -z "$DYNAMIC" ]; then
    # If to tail
    if [ -z "$TAIL" ]; then
        exec supervisord -c /home/docker/omg-monitor/config/supervisor.conf
    else
        supervisord -c /home/docker/omg-monitor/config/supervisor.conf &
        multitail --mergeall -Q 1 $LOG_DIR/*
    fi
else
    # If to tail
    if [ -z "$TAIL" ]; then
        exec supervisord -c /home/docker/omg-monitor/config/supervisor_dynamic.conf
    else
        supervisord -c /home/docker/omg-monitor/config/supervisor_dynamic.conf &
        multitail --mergeall -Q 1 $LOG_DIR/*
    fi
fi
