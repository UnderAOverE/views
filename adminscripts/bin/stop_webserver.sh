#!/usr/bin/env bash

#
# name: stop_webserver.sh
# author: Shane Reddy
# dob: 12/05/2019
# version: 1.0.1v
# details: stop script for SimpleHTTP python web server.
# contact: shane.reddy@ttiinc.com
#
# modifications: (12/05/2019 1.0.0v) initial version.
#                (02/04/2020 1.0.1v) PID return 'null', updated the code to catch 'null'.
#
#

######################################################################################################################
# initialization.
######################################################################################################################
home_plate=/home/sreddy/adminscripts #make sure this is updated if copying to a different server or path

######################################################################################################################
# main.
######################################################################################################################
pid_number=$(ps -ef | grep webserver.py | grep -v grep | awk '{print $2}')
if [[ ${pid_number}x == "x" ]]; then
    echo "WARN| SimpleHTTP web server is not running."
else
    kill -9 ${pid_number}
    sleep 5
    ps -ef | grep webserver.py | grep -v grep >/dev/null 2>&1
    if [[ $? -eq 0 ]]; then
        echo "WARN| SimpleHTTP web server still running, manually kill the PID please."
    else
        echo "INFO| SimpleHTTP web server is stopped now."
    fi
fi

#end_stop_webserver.sh
