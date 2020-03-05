#/usr/bin/env python

#
#
#
# name: app_ready.py
# author: Shane Reddy
# version: 1.2.0v
# dob: 12/27/2019
# explanation: tool to make HTTP requests to application for health check. Tested with below URLs:
#         is_app_ready("CAM Development", "http://txjbst01.ttiinc.com:8180/cam/#/", "401")
#         is_app_ready("Express Development 1", "http://10.1.63.85:8230/httpSession/login.html", "200")
#         is_app_ready("Express Development 2", "http://10.1.63.89:8230/httpSession/login.html", "200")
#
# dependencies: python >= 2.7v + urllib2
# modifications: (12/27/2019 1.0.0v) initial version.
#                (12/31/2019 1.1.0v) added 404.
#                (01/09/2020 1.2.0v) added 'expected_http_code'.
#
# contact: shane.reddy@ttiinc.com
#
######################################################################################################################

######################################################################################################################
# initialization & global imports
######################################################################################################################
import urllib2, sys, socket, ssl

######################################################################################################################
# Defs.
######################################################################################################################
def is_app_ready(appname, url, http_code, timeout=2):
    context = ssl._create_unverified_context()
    try:
        #print("INFO| application '%s' start complete.") %(appname)
        if urllib2.urlopen(url, timeout=timeout, context=context).getcode() == 200: return 0
    except urllib2.URLError as e:
        if str(e).find(http_code) != -1: return 0
        return 1
    except socket.timeout as e:
        return 1
    #endTryExcept
#endDef

######################################################################################################################
# Main.
######################################################################################################################
if __name__== "__main__":
    if len(sys.argv) == 4:
        app_name=sys.argv[1]
        URL=sys.argv[2]
        expected_http_code=sys.argv[3]
        print(is_app_ready(app_name, URL, expected_http_code))
    else:
        print("ERROR| provide Application name, URL & HTTP Code.")
        print("INFO| python app_ready.py \"Express QA\" \"http://devexpress.ttiinc.com\" \"200\"")
        sys.exit(1)
    #endIfElse
#endIf

#end_app_ready.py
