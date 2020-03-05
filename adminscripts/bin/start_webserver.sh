#!/usr/bin/env bash

#
# name: start_webserver.sh
# author: Shane Reddy
# dob: 12/05/2019
# version: 1.0.0v
# details: start script for SimpleHTTP python web server.
# contact: shane.reddy@ttiinc.com
#
# modifications:
#
#

######################################################################################################################
# initialization
######################################################################################################################
home_plate=/home/sreddy/adminscripts #make sure this is updated if copying to a different server or path

######################################################################################################################
# main
######################################################################################################################
nohup python ${home_plate}/py/webserver.py 2>${home_plate}/logs/webserver.err 1>${home_plate}/logs/webserver.out &
sleep 5
ps -ef | grep webserver.py | grep -v grep >/dev/null 2>&1
if [[ $? -eq 0 ]]; then
    echo "INFO| SimpleHTTP web server is running now."
else
    echo "WARN| SimpleHTTP web server falied to start, manually start the process please."
fi

#end_start_webserver.sh