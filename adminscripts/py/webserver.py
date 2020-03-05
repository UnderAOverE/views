#!/usr/bin/env python

#
#
# name: webserver.py
# author: Shane Reddy
# version: 1.0.0v
# dob: 12/05/2019
# explanation: SimpleHTTP python web server.
# dependencies:
# modifications:
#
# contact: shane.reddy@ttiinc.com
#
#
######################################################################################################################

######################################################################################################################
# initialization & global imports (below path needs to be updated accordingly)
######################################################################################################################
import SimpleHTTPServer
import SocketServer, os

documentRoot="/home/sreddy/adminscripts/web"
Port=8000
__author__="shanereddy"

######################################################################################################################
# Main.
######################################################################################################################
os.chdir(documentRoot)
Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
httpd = SocketServer.TCPServer(("", Port), Handler)
httpd.serve_forever()

#end_webserver.py
