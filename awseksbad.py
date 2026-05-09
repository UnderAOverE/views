
{
  "target_key": "",
  "platform": "genfire",
  "identifiers": {
    "cluster": "",
    "application": "",
    "environment": "",
    "datacenter": "",
    "extras": {}
  },
  "source": {
    "type": "appdynamics",
    "controller_ref": "",
    "credential_key": "ampchat",
    "appd_application_path": "",
    "metric_path": ""
  },
  "tunables": {
    "poll_interval_minutes": 5,
    "lookback_minutes": 5,
    "capture_full_stats": true
  },
  "notification_routing": {
    "recipients_to": [],
    "recipients_bcc": [],
    "recipients_cc": [],
    "enabled": true
  },
  "filters": {
    "instance_include": [],
    "instance_exclude": [],
    "metric_include": [
      "RegisteredCQCount",
      "JVMPauses",
      "QueryRequestRate",
      "ClientConnectionCount",
      "AverageWrites",
      "NumSubscriptions",
      "TotalRegionEntryCount",
      "PutAllRate",
      "AverageReads",
      "ServerLocator",
      "MaximumHeapSize",
      "GarbageCollectionCount",
      "GarbageCollectionTime",
      "PutsRate",
      "GetsRate",
      "NumThreads",
      "CpuUsage",
      "CurrentHeapSize",
      "TotalHeapSize",
      "UsedMemory"
    ]
  },
  "enabled": true
}


https://appdync-nam-gcg-p2.wlb2.net:8090/controller/rest/applications/Database Monitoring/metric-data
?metric-path=Databases|*|*|*
&time-range-type=BEFORE_NOW
&duration-in-mins=60
&output=json

{
    "metricId": 2645900,
    "metricName": "DB|Server Statistic|user calls",
    "metricPath": "Databases|168066_WALLET_NAM_PRD(GPDWLTP)|Server Statistic|user calls",
    "frequency": "ONE_MIN",
    "metricValues": [
        {
            "startTimeInMillis": 1778041200000,
            "occurrences": 0,
            "current": 7841,
            "min": 0,
            "max": 0,
            "useRange": false,
            "count": 180,
            "sum": 667639,
            "value": 11127,
            "standardDeviation": 0
        }
    ]
}


https://appdync-nam-gcg-pr3.wlb2.net:8090/controller/rest/applications/175221 Apigee NAM PRD/metric-data
?metric-path=Application Infrastructure Performance|*|Individual Nodes|*|*|*
&time-range-type=BEFORE_NOW
&duration-in-mins=10
&output=json

{
    "metricId": 8728531,
    "metricName": "Hardware Resources|Memory|Total (MB)",
    "metricPath": "Application Infrastructure Performance|APIGEE_PRD8|Individual Nodes|sd-3bef-74aa_router|Hardware Resources|Memory|Total (MB)",
    "frequency": "ONE_MIN",
    "metricValues": [ {
        "startTimeInMillis": 1778153880000,
        "occurrences": 0,
        "current": 63886,
        "min": 63886,
        "max": 63886,
        "useRange": true,
        "count": 1200,
        "sum": 7663200,
        "value": 63886,
        "standardDeviation": 0
    } ]
},
{
    "metricId": 9198575,
    "metricName": "METRIC DATA NOT FOUND",
    "metricPath": "Application Infrastructure Performance|MCAG|Individual Nodes|sd-8f7b-e29b_MCAgent|Agent|BCI|Average Time to Create ClassMetaData (ms)",
    "frequency": "ONE_MIN",
    "metricValues": [ ]
},
{
    "metricId": 8728585,
    "metricName": "JVM|Garbage Collection|Freed-Objects (MB)",
    "metricPath": "Application Infrastructure Performance|APIGEE_PRD7|Individual Nodes|sd-b452-5cf7_mp|JVM|Garbage Collection|Freed-Objects (MB)",
    "frequency": "ONE_MIN",
    "metricValues": [ {
        "startTimeInMillis": 1778153880000,
        "occurrences": 0,
        "current": 56037,
        "min": 42683,
        "max": 59164,
        "useRange": true,
        "count": 60,
        "sum": 3091968,
        "value": 51533,
        "standardDeviation": 0
    } ]
}




https://appdyn-nam-gcg-prod-1.net:8090/controller/rest/applications/169196 FUSION COMMERCIAL NAM PRD/metric-data
?metric-path=Application Infrastructure Performance|MCAG|Individual Nodes|*|JMX|*|*
&time-range-type=BEFORE_NOW
&duration-in-mins=5
&output=json

https://appdync-nam-gcg-p8.cloudgsl.net:8090/controller/rest/applications/171532 DIGITALNEXGEN-IES SWDC NAM PRD/metrics
?metric-path=Application Infrastructure Performance|GEMFIRE|Individual Nodes|*|JMX|*|*
&time-range-type=BEFORE_NOW
&duration-in-mins=5
&output=json

{
    "metricId" : 5484866,
    "metricName" : "server|Component:1643|JMX|GemFire_System:Distributed|AverageReads",
    "metricPath" : "Application Infrastructure Performance|GEMFIRE|Individual Nodes|sd-7be6-ff35|JMX|GemFire_System|Distributed|AverageReads",
    "frequency" : "ONE_MIN",
    "metricValues" : [ {
        "startTimeInMillis" : 1778152440000,
        "occurrences" : 0,
        "current" : 1275,
        "min" : 496,
        "max" : 1275,
        "useRange" : true,
        "count" : 60,
        "sum" : 44736,
        "value" : 746,
        "standardDeviation" : 0
    } ]
}




{
  "_comment": "NAM Sales Splunk: hosts, ports, FIDs & connection details",
  "sector": "Sales",
  "region": "NAM",
  "environments": [
    {
      "name": "production",
      "server_port_pairs": "splunk-search-rest.wlb.net:8089",
      "fid_details": [
        {
          "name": "aichat",
          "decrypter_key": "xxx",
          "decrypter_token": "xxx"
        },
        {
          "name": "aichat_digital",
          "decrypter_key": "xxx",
          "decrypter_token": "xxx"
        },
        {
          "name": "aichat_dna",
          "decrypter_key": "xxx",
          "decrypter_token": "xxx"
        }
      ],
      "search_heads": [
        "10.3.179.182",
        "10.3.179.183",
        "10.18.104.179",
        "10.50.246.81",
        "10.50.246.88",
        "10.95.178.148"
      ],
      "ssl": {
        "ca_certs": "lib/ca-prod.pem",
        "enable": true
      }
    },
    {
      "name": "warehouse-production",
      "server_port_pairs": "splunk-search-warehouse.wlb.net:8089",
      "fid_details": [
        {
          "name": "aichat",
          "decrypter_key": "xxx",
          "decrypter_token": "xxx"
        }
      ]
    }
  ]
}


{
  "controller": {
    "name": "GCG-NA-PRD1",
    "sector": "Sales",
    "region": "NAM",
    "environment": "production",
    "enable": true,
    "url": "https://appdyn-nam-gcg-prod-1.net",
    "account": "customer1",
    "oauth2": {
      "method": "POST",
      "port": 8090,
      "headers": {
        "Content-Type": "application/vnd.appd.cntrl+protobuf",
        "v": "1"
      },
      "path": "controller/api/oauth/access_token",
      "credentials": {
        "aichat_namcore": {
          "secret_key": "xxx",
          "secret_token": "xxx",
          "bearer_token": "xxx",
          "bearer_token_expiration": {
            "$date": "2026-04-21T00:30:07.832Z"
          }
        },
        "aichat": {
          "secret_key": "xxx",
          "secret_token": "xxx",
          "bearer_token": "xxx",
          "bearer_token_expiration": {
            "$date": "2026-04-21T00:30:07.862Z"
          }
        }
      }
    },
    "timeout": 60
  }
}

