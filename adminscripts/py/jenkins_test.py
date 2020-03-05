import urllib.request, json
import time

jenkins_url="http://txcomt11:8080"

with urllib.request.urlopen(jenkins_url+"/api/json?tree=jobs[name]") as url1:
    data = json.loads(url1.read().decode())
    for job_id in range(0, (len(data["jobs"]))):
        job_name = data["jobs"][job_id]["name"]
        try:
            with urllib.request.urlopen(jenkins_url+"/job/"+job_name+"/lastBuild/api/json?tree=timestamp") as url2:
                jdata = json.loads(url2.read().decode())
                timeL = jdata["timestamp"]
                timenepoch=time.strftime('%m/%d/%Y,%H:%M:%S', time.localtime(timeL/1000)) 
                #print(job_name+" "+str(timeL))
                print(job_name+","+timenepoch)
            #endWith
        except:
            #print("There are no builds perfomed for this job: "+job_name)
            print(job_name+",00/00/0000,00:00:00")
        #endTryExcept
    #endFor
#endWit