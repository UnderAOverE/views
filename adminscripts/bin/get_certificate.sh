#!/usr/bin/env bash

#
#
# name: get_certificate.sh
# explanation: script to ping the server and port and print only interesting stuff.
# dependencies: openssl & /var/tmp directory.
# contact: shane.reddy@ttiinc.com
# dob: 12/09/2019
# author: Shane Reddy
# version: 1.0.1v
# modifications: (12/09/2019 1.0.0v) initial version.
#                (12/12/2019 1.0.1v) openssl waits for user input, added echo | to close the connection.
#
#
#

# initialization.
server_name=${1}
server_port=${2}

# main
if [[ $# -eq 2 ]]; then
    timeout 1 bash -c "</dev/tcp/${server_name}/${server_port}" >/dev/null 2>&1
    if [[ $? -eq 0 ]]; then
        echo | openssl s_client -connect ${server_name}:${server_port} >/dev/null 2>&1
        if [[ $? -eq 0 ]]; then
            echo | openssl s_client -connect ${server_name}:${server_port} 2>/dev/null </dev/null \
              | sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p' 1>/var/tmp/certificate_generated_from_get_certificate_sh.txt; \
              echo | openssl x509 -in /var/tmp/certificate_generated_from_get_certificate_sh.txt -noout -text \
              | egrep "Signature Algorithm|Issuer|Not Before|Not After|Subject\:" \
              | grep -v "CA Issuers" \
              | head -5; \
              echo | openssl x509 -in /var/tmp/certificate_generated_from_get_certificate_sh.txt -noout -serial
              rm /var/tmp/certificate_generated_from_get_certificate_sh.txt
              exit 0
        else
            echo "WARN| ${server_port} is not secured on ${server_name}."
            exit 0
        fi
    else
        echo "ERROR| ${server_port} not opened on ${server_name}."
        exit 1
    fi
else
    echo "ERROR| provide servername and port number"
    exit 1
fi

#end_get_certificate.sh