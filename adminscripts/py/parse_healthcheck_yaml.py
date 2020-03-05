import yaml, sys

#
#
# name: parse_healthcheck_yaml.py
# author: Shane Reddy
# version: 1.0.0v
# dob: 12/05/2019
# explanation: tool helps parse inventory.yaml file and feeds the output to health_check.sh.
# dependencies: yaml
# modifications:
#
# contact: shane.reddy@ttiinc.com
#
#
######################################################################################################################

######################################################################################################################
# initialization (below path needs to be updated accordingly)
######################################################################################################################
finalListDirectory="/home/sreddy/adminscripts/props"
err_file=finalListDirectory+"/../logs/hc_err.log"
__author__="shanereddy"

######################################################################################################################
# main
######################################################################################################################
if __name__== "__main__":
    if len(sys.argv) == 1:
        print("ERROR| provide the yaml file path.")
        sys.exit(1)
    #endIf
    yaml_file=sys.argv[1]
    with open(yaml_file, 'r') as stream:
        try:
            data=yaml.safe_load(stream)
            try:
                for Key in data:
                    finalListFile=finalListDirectory+"/"+Key+".properties"
                    with open(finalListFile, "w") as fL:
                        fL.write("")
                    #endWith
                    try:
                        for eKey in data[Key]:
                            try:
                                for kValueIndex in range(0, len(data[Key][eKey])):
                                    #print(Key+":"+eKey+":"+data[Key][eKey][kValueIndex])
                                    with open(finalListFile, "a") as fL:
                                        fL.write(eKey+":"+data[Key][eKey][kValueIndex]+"\n")
                                    #endWith
                                #endFor
                            except:
                                #print("WARNING| no servers defined for "+Key+".")
                                with open(err_file, "a") as eL:
                                    eL.write("WARNING| no servers defined for "+Key+" under "+eKey+".\n")
                                #endWith
                            #endTryExcept
                        #endFor
                    except:
                        #print("ERROR| safe.load returned no ekeys for "+Key+".")
                        with open(err_file, "a") as eL:
                            eL.write("ERROR| safe.load returned no ekeys for "+Key+".\n")
                        #endWith
                        #sys.exit(1)
                    #endTryExcept
                #endFor
            except:
                #print("ERROR| safe.load returned no keys.")
                with open(err_file, "a") as eL:
                    eL.write("ERROR| safe.load returned no keys.\n")
                #endWith
                #sys.exit(1)
            #endTryExcept
        except yaml.YAMLError as Exception:
            print(Exception)
        #endTryExcept
    #endWith
#endIf

#end_parse_healthcheck_yaml.py