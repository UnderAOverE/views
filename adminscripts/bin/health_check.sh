#!/usr/bin/env bash

#
#
#
# name: health_check.sh
# author: Shane Reddy
# version: 3.1.0v
# dob: 12/05/2019
# explanation: tool to ping the application ports to check app servers health.
#
# dependencies: bash, firewall open, mail, python, inventory.yaml, app_ready.py & parse_healthcheck_yaml.py
# modifications: (12/05/2019 1.0.0v) initial version.
#                (12/31/2019 2.0.0v) added historical data status for past 2 hours & application ready URL check.
#                (01/06/2020 2.1.0v) changed 'Up' to 1 and 'Down' to 0 for cleaner look.
#                (01/09/2020 3.0.0v) updated the app_ready with user inputed http codes,
#                                    added send_email to alert the admins,
#                                    added PyamentProcessing to the inventory &
#                                    added anchor reference.
#                (02/26/2020 3.1.0v) removed Shaun Tate and added Lesley Oredia.
#
# contact: shane.reddy@ttiinc.com
#
#
#
######################################################################################################################

######################################################################################################################
# initialization
# inventory file should contain servername and the port to check.
# ex: environment:server1.com:443
# commented entries are ignored
######################################################################################################################
home_plate=/home/sreddy/adminscripts #make sure this is updated if copying to a different server or path.
inventory_files_directory=${home_plate}/props
log_file=${home_plate}/logs/hc_main.log
yaml_file=${home_plate}/conf/inventory.yaml
run_time=$(date +%m/%d/%Y\ %H:%M:%S\ %Z)
temp_directory=${home_plate}/temp

# flaf to send mail.
send_mail_to_admin=0

######################################################################################################################
# functions
######################################################################################################################
function Echo {
    echo "$@" | tee -a ${home_plate}/web/index.html
}

function mEcho {
    echo "$@" >> ${temp_directory}/mail.out
}

function mail_html_1 {
    cp /dev/null ${temp_directory}/mail.out
    mEcho "To: shane.reddy@ttiinc.com;lesley.oredia@ttiinc.com;nickolas.owen@ttiinc.com;brad.cooke@ttiinc.com"
    mEcho "From: shane.reddy@ttiinc.com"
    mEcho "Subject: Application Health Alert!"
    mEcho "Content-Type: text/html"
    mEcho "<html>
    <head>
        <title>Middleware & DevOps - Application Health Alert</title>
        <style>
            table, th, td {
                border: 1px solid black;
                border-collapse: collapse;
                text-align:center;
                margin-left:auto;
                margin-right:auto;
            }
            th, td {
                padding: 1px;
            }
        </style>
    </head>
    <body>
        <br>
        <table style='width:50%'>
            <tr bgcolor='#29BC3F'>
                <th>Servername</th>
                <th>JVM</th>
                <th>Website</th>
                <th>Status</th>
            </tr>"
}

function mail_html_3 {
    mEcho "        </table>
        <br><br>
        <h4><a href="http://txjnkp01.ttiinc.com:8000/index.html">Middleware & DevOps TeamWiki</a></h4>
    </body>
    </html>"
}

function mail_html_2 {
    server_name=${1}
    jvm_name=${2}
    url_=${3}
    mEcho "        <tr>
                <td>${server_name}</td>
                <td>${jvm_name}</td>
                <td>${url_}</td>
                <td>Down</td>
            </tr>"
}

function send_mail {
    cat ${temp_directory}/mail.out | /usr/sbin/sendmail -t
}

function page_section1 {
    Echo "<!DOCTYPE html>"
    Echo "<html lang=\"en\">"
    Echo "  <head>"
    Echo "          <!-- ======================================================================================================== -->"
    Echo "          <meta charset=\"utf-8\">"
    Echo "          <meta http-equiv=\"X-UA-Compatible\" content=\"IE=edge\">"
    Echo "          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1, shrink-to-fit=no\">"
    Echo "          <!-- The above 3 meta tags *must* come first in the head; any other head content must come *after* these tags -->"
    Echo "          <meta name=\"description\" content=\"Infrastructure Systems Wiki Page\">"
    Echo "          <meta name=\"author\" content=\"Shane Reddy\">"
    Echo "          <link rel=\"icon\" href=\"img/favicon.ico\">"
    Echo "          <title>Middleware & DevOps TTI Inc.</title>"
    Echo "          <script type = \"text/javascript\">"
    Echo "                  if((navigator.vendor.length > 5) && (navigator.vendor.toLowerCase().indexOf(\"google inc\") > -1)) {"
    Echo "                          console.log(\"Chrome detected.\");"
    Echo "                  } else {"
    Echo "                          window.location.href = \"code/berror.html\"; // all other browsers"
    Echo "                  }"
    Echo "          </script>"
    Echo "          <!-- Bootstrap Core CSS -->"
    Echo "          <link href=\"code/css/bootstrap.min.css\" rel=\"stylesheet\">"
    Echo "          <link href=\"code/css/dashboard.css\" rel=\"stylesheet\">"
    Echo "          <link href=\"code/css/filter.css\" rel=\"stylesheet\">"
    Echo "          <link href=\"code/css/wiki-custom.css\" rel=\"stylesheet\">"
    Echo "          <!-- ======================================================================================================== -->"
    Echo "  </head>"
    Echo "  <body>"
    Echo "          <nav class=\"navbar navbar-default navbar-inverse navbar-fixed-top\">"
    Echo "                  <div class=\"container-fluid\">"
    Echo "                          <!-- Brand and toggle get grouped for better mobile display -->"
    Echo "                          <div class=\"navbar-header\">"
    Echo "                                  <button type=\"button\" class=\"navbar-toggle collapsed\" data-toggle=\"collapse\" data-target=\"#bs-example-navbar-collapse-1\" aria-expanded=\"false\">"
    Echo "                                          <span class=\"sr-only\">Toggle navigation</span>"
    Echo "                                          <span class=\"icon-bar\"></span>"
    Echo "                                          <span class=\"icon-bar\"></span>"
    Echo "                                          <span class=\"icon-bar\"></span>"
    Echo "                                  </button>"
    Echo "                                  <a class=\"navbar-brand\" href=\"#\">"
    Echo "                                  <img alt=\"Brand\" src=\"img/tti.png\">"
    Echo "                                  </a>"
    Echo "                          </div>"
    Echo "                          <h4 class=\"navbar-text tcenter\"> Infrastructure Services Wiki Page</h4>"
    Echo "                          <!-- Collect the nav links, forms, and other content for toggling -->"
    Echo "                          <div class=\"collapse navbar-collapse\" id=\"bs-example-navbar-collapse-1\">"
    Echo "                                  <ul class=\"nav navbar-nav\">"
    Echo "                                          <li class=\"active\"><a href=\"#\">Home <span class=\"sr-only\">(current)</span></a></li>"
    Echo "                                          <li class=\"dropdown\">"
    Echo "                                                  <a href=\"#\" class=\"dropdown-toggle\" data-toggle=\"dropdown disabled\" role=\"button\" aria-haspopup=\"true\" aria-expanded=\"false\">&nbsp;&nbsp;&nbsp;&nbsp;Servers <span class=\"caret\"></span>&nbsp;&nbsp;&nbsp;&nbsp;</a>"
    Echo "                                                  <ul class=\"dropdown-menu\">"
    Echo "                                                          <li><a href=\"data/cam/cammain.html\">Customer Account Management (CAM)</a></li>"
    Echo "                                                          <li><a href=\"data/hats/hatsmain.html\">HATS</a></li>"
    Echo "                                                          <li><a href=\"data/oms/omsmain.html\">OMS</a></li>"
    Echo "                                                          <li><a href=\"data/express/xpmain.html\">Express</a></li>"
    Echo "                                                          <li><a href=\"data/qd/qdmain.html\">Quote Dashboard</a></li>"
    Echo "                                                          <li><a href=\"data/pp/ppmain.html\">PaymentProcessing</a></li>"
    Echo "                                                  </ul>"
    Echo "                                          </li>"
    Echo "                                          <li class=\"dropdown\">"
    Echo "                                                  <a href=\"#\" class=\"dropdown-toggle\" data-toggle=\"dropdown\" role=\"button\" aria-haspopup=\"true\" aria-expanded=\"false\">Applications <span class=\"caret\"></span></a>"
    Echo "                                                  <ul class=\"dropdown-menu\">"
    Echo "                                                          <li><a href=\"data/cam/camservers.html\">Customer Account Management (CAM)</a></li>"
    Echo "                                                          <li><a href=\"data/hats/hatsservers.html\">HATS</a></li>"
    Echo "                                                          <li><a href=\"data/oms/omsservers.html\">OMS</a></li>"
    Echo "                                                          <li><a href=\"data/express/xpservers.html\">Express</a></li>"
    Echo "                                                          <li><a href=\"data/qd/qdservers.html\">Quote Dashboard</a></li>"
    Echo "                                                          <li><a href=\"data/pp/ppservers.html\">PaymentProcessing</a></li>"
    Echo "                                                  </ul>"
    Echo "                                          </li>"
    Echo "                                  </ul>"
    Echo "                                  <!--<form class=\"navbar-form navbar-left\">"
    Echo "                                          <div class=\"form-group\">"
    Echo "                                                  <input type=\"text\" class=\"form-control\" placeholder=\"Search...\">"
    Echo "                                          </div>"
    Echo "                                          <button type=\"submit\" class=\"btn btn-default\">Submit</button>"
    Echo "                                  </form>"
    Echo "                                  -->"
    Echo "                                  <ul class=\"nav navbar-nav navbar-right\">"
    Echo "                                          <li class=\"disabled\"><a href=\"#\">Report Error </a></li>"
    Echo "                                  </ul>"
    Echo "                          </div> <!-- /.navbar-collapse -->"
    Echo "                  </div> <!-- /.container-fluid -->"
    Echo "          </nav>"
    Echo "          <div class=\"custom-position\">"
    Echo "          <h1>&nbsp; <u>Application Servers Health Check Page</u>&nbsp;&nbsp;&nbsp; (${run_time})</h1>"
    Echo "                  <div class=\"container-fluid\">"
    Echo "                          <input type=\"text\" id=\"filterInput\" onkeyup=\"filterFunction()\" placeholder=\" Enter Application Name...\">"
    Echo "                          <div class=\"table-responsive\">"
    Echo "                                  <table class=\"table table-striped table-hover table-bordered\" id=\"filterTable\">"
    Echo "                                          <thead>"
    Echo "                                                  <tr class=\"header\">"
    Echo "                                                          <th>Application Name</th>"
    Echo "                                                          <th>Environment</th>"
    Echo "                                                          <th>Server Name (JVM Name)</th>        "
    Echo "                                                          <th>Status [15 minutes intervals]<br>0:15:30:45:60:75:90:105:120</th>"
    Echo "                                                          <th>Application Ready?</th>"
    Echo "                                                          <th>Website</th>"
    Echo "                                                  </tr>"
    Echo "                                          </thead>"
}

function page_section2 {
    echo "under construction..."
}

function page_section3 {
    Echo "                    </table>"
    Echo "                </div>"
    Echo "            </div>"
    Echo "        </div>"
    Echo "        <!-- ================================================== -->"
    Echo "        <!------------- Bootstrap Core JavaScript ---------------->"
    Echo "        <!-- ================================================== -->"
    Echo "        <script src=\"code/js/jquery-3.1.1.min.js\"></script>"
    Echo "        <script src=\"code/js/tether.min.js\"></script>"
    Echo "        <script src=\"code/js/bootstrap.min.js\"></script>"
    Echo "        <script src=\"code/js/filter.js\"></script>"
    Echo "    </body>"
    Echo "</html>"
}

######################################################################################################################
# main
######################################################################################################################
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) healthcheck.sh --> begin" >> ${log_file}
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${home_plate}/py/parse_healthcheck_yaml.py --> begin" >> ${log_file}
python ${home_plate}/py/parse_healthcheck_yaml.py ${yaml_file} >/dev/null 2>&1
[[ $? -eq 0 ]] || { echo "ERROR| parse_healthcheck_yaml.py returned non-zero!" ; exit 1 ; }
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${home_plate}/py/parse_healthcheck_yaml.py --> 0" >> ${log_file}
cp /dev/null ${home_plate}/web/index.html
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${home_plate}/web/index.html --> reset" >> ${log_file}
page_section1
mail_html_1
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) page_section --> 0" >> ${log_file}
for iFile in $(ls ${inventory_files_directory}); do
    application_name=$(echo ${iFile} | awk -F "." '{print $1}')
    for Line in $(cat ${inventory_files_directory}/${iFile}); do
        server_name=$(echo ${Line} | awk -F ":" '{print $2}')
        server_env=$(echo ${Line} | awk -F ":" '{print $1}')
        server_port=$(echo ${Line} | awk -F ":" '{print $3}')
        jvm_name=$(echo ${Line} | awk -F ":" '{print $4}')
        snooze_alert=$(echo ${Line} | awk -F ":" '{print $5}')
        timeout 1 bash -c "</dev/tcp/${server_name}/${server_port}" >/dev/null 2>&1
        if [[ $? -eq 0 ]]; then
            server_status="1"
        else
            server_status="0"
        fi
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.0;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.15;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.30;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.45;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.60;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.75;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.90;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.105;
        touch ${temp_directory}/${application_name}_${server_name}_${jvm_name}.120
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.105 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.120
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.90 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.105
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.75 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.90
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.60 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.75
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.45 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.60
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.30 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.45
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.15 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.30
        cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.0 > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.15
        echo "${server_status}" > ${temp_directory}/${application_name}_${server_name}_${jvm_name}.0
        #historical_data ${server_status} ${application_name} ${jvm_name}
        server_website="http://${server_name}:${server_port}"
        sserver_website="https://${server_name}:${server_port}"
        historical_data_statusx=$(cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.0;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.15;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.30;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.45;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.60;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.75;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.90;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.105;cat ${temp_directory}/${application_name}_${server_name}_${jvm_name}.120)
        historical_data_status=$(echo ${historical_data_statusx} | sed "s/ /\//g")
        Echo "                        <tbody>"
        Echo "                            <tr>"
        Echo "                                <td class=\"col-md-2\">${application_name}</td>"
        Echo "                                <td class=\"col-md-2\">${server_env}</td>"
        Echo "                                <td class=\"col-md-2\">${server_name} (${jvm_name})</td>"
        Echo "                                <td class=\"col-md-2\">${historical_data_status}</td>"
        if [[ ${application_name} == "OppurtunityManagementSystem" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "OppurtunityManagementSystem" "${server_website}/oms/api" "404")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}/oms/api"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}/oms/api." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/oms/api\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "CustomerAccountManagement" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "CustomerAccountManagement" "${server_website}/cam/#/" "401")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}/cam/#/"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}/cam/#/." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/cam/#/\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "HATS" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "HATS" "${server_website}/TTIBPA" "200")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}/TTIBPA"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}/TTIBPA." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/TTIBPA/\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "SupplyChain" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "SupplyChain" "${server_website}" "404")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "Express" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "Express" "${sserver_website}/wasPerfTool/" "404")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}/wasPerfTool/"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}/wasPerfTool/." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${sserver_website}/wasPerfTool/\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "ExpressEAP" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "ExpressEAP" "${server_website}" "404")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "QuoteDashboard" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "QuoteDashboard" "${server_website}/quoteDashboard" "401")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}/quoteDashboard"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}/quoteDashboard." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/quoteDashboard\" target="_blank">Click Here</a></td>"
        fi
        if [[ ${application_name} == "PaymentProcessing" ]]; then
            app_ready=$(python ${home_plate}/py/app_ready.py "PaymentProcessing" "${server_website}/PaymentProcessor" "401")
            if [[ ${app_ready} -eq 0 ]]; then
                Echo "                                <td class=\"col-md-2\">Yes</td>"
            else
                Echo "                                <td class=\"col-md-2\">No</td>"
                if [[ ${snooze_alert} -eq 0 ]]; then
                    mail_html_2 "${server_name}" "${jvm_name}" "${server_website}/PaymentProcessor"
                    send_mail_to_admin=1
                else
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) below connection string reported as down" >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) ${server_name} ${jvm_name} ${server_website}/PaymentProcessing." >> ${log_file}
                    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) alert snoozed." >> ${log_file}
                fi
            fi
            Echo "                                <td class=\"col-md-2\"><a href=\"${server_website}/PaymentProcessor\" target="_blank">Click Here</a></td>"
        fi
        Echo "                            </tr>"
        Echo "                        </tbody>"
    done
done
page_section3
mail_html_3
if [[ ${send_mail_to_admin} -eq 1 ]]; then
    send_mail
    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) called 'sent mail'." >> ${log_file}
else
    echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) send_mail_to_admin set to ${send_mail_to_admin}." >> ${log_file}
fi
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) page_section3 --> 0" >> ${log_file}
echo "-> $(date +[%m/%d/%Y\ %H:%M:%S\ %Z]) health_check.sh --> done" >> ${log_file}
echo >> ${log_file}

#end_health_check.sh
