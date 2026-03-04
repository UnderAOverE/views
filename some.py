Here I have 5 million records inside my source collection (Certificates) like below:
'''
"cn","US","See2a6c9f6542a4736ffb76516bfe3",7,2026-03-09T00:00:00.000000+0000,170644,Activated,SSL Tracker,null,null,null,null,null,null,null,null
"cn","US","See2a6c9f6542a4736ffb76516bfe3",7,2026-03-09T00:00:00.000000+0000,178961,null,HashiCorp,namgcbgtd42p_gcb-nam-iam-ccp-178961_gtlecsprod-xlg-sct-p-sts-ob-canary,null,null,null,null,null,N/A,null



cbnasalesforceprod.chasebank.com,0d104880343fb3f6b8ffbc00b8ae0390a,15,2026-03-20T00:00:00.000000+0000,18550,Retired,SSL Tracker,null,null,null,null,null,null,null,null
cbnasalesforceprod.chasebank.com,07f738d5bf0766b0c1306b6850d57f1f8,314,2027-01-19T00:00:00.000000+0000,163016,Retired,SSL Tracker,null,null,null,null,null,null,null,null
cbnasalesforceprod.chasebank.com,0dce0db3bd10080c880acc13aad1a54d,330,2027-01-29T00:00:00.000000+0000,163016,Retired,SSL Tracker,null,null,null,null,null,null,null,null
cbnasalesforceprod.chasebank.com,07da4c7cd6d0957e2023896bfc4cb49cb,355,2027-02-23T00:00:00.000000+0000,176550,Retired,SSL Tracker,null,null,null,null,null,null,null,null
cbnasalesforceprod.chasebank.com,0dce0db3bd10080c880acc13aad1a54d,331,2027-01-29T23:59:59.000000+0000,null,VALCRED,,,,,,,
cbnasalesforceprod.chasebank.com,0dce0db3bd10080c880acc13aad1a54d,331,2027-01-29T23:59:59.000000+0000,null,VALCRED,,,,,,,
http://127.10.10.1:7750/idoc/service/
https://chaseriskcommercialidoc.wlb2.nam.nsroot.net/idoc/service/secure/SF/requirement/v3/submit

GCG-CBNA-SalesForce-ACL,"SGGOutboundApplicationDomain,/idoc/*"
GCG-SalesForce-Sign-ACL,"GCGApplicationDomain,/idoc/*"
GCG-CBNARetail-SalesForce-169883-ACL,"SGGOutboundApplicationDomain,/idoc/*"



'''
```
{"distinguished_name":"171384.boss.dev","start_date":"null","expiration_date":{"$date":"2027-03-11T00:00:00.000Z"},"csi_application_id":171384,"status":"Valid","days_to_expiration":546,"source_properties":{"name":"HashiCorp","serial_number":"690002ee5bd989e475c9d4e3fa00000002ee5b","certificate_type":"jks","certificate_owner":"null","certificate_name":"null","owner_email":"null","support_group":"null","support_group_email":"null","application_manager":"null","l3_application_head":"null","l4_application_head":"null","environment":"DEV","evolven_host":"null","evolven_path":"null","ssg_domain":"null","ssg_url_in":"null","ssg_url_out":"null","internal_ssg_domain":"null","ssg_url":"null","san_names":"null","instance_name":"N/A","microservice_name":"namcgbgtd25d_gcb-nam-wmt-retail-171384_gtlecsdev3-pdm-o-accountlinking-usretail","openshift_namespace":"null","openshift_container":"null","ssl_cm_region":"NAM","ssl_cm_sector":"PBWM","ssl_cm_status":"null","lob_domain":"NAM_Core","TechnologyManagedSegment_L6":"USPB Technology [L6]","TechnologyManagedSegment_L7":"Digital [L7]","ApplicationManager":"XXXXXX","ApplicationManager_soEid":"XXXXXX","Level3Head":"XXXXXX","Level4Head":"XXXXXX","Level5Head":"XXXXXX","SupportManager":"XXXXXX","Domain":"NAM_Core","SubDomain":"Assisted Channels","LOB":"RETAIL"},"log_date":{"$date":"2025-09-10T06:33:13.311Z"}}
```

Now my goal is to extract certificates that are expiring in 7 days (this should be editable) and also that have "source_propertie.microservice_name" not equal to "null" (for some reason thisis actually a string null)
Please note the microservice_name is clustername_projectname_deploymentname(or statefulsetname), once you have all that data, this is what need to do...

Lets say a microservice_name called cluster1_project1_deployment1, construct below document to be inserted (collection name you suggest)

certificate model:
```
{
  "distinguished_name": "xxxxxxxxxxxx",
  "days_to_expiration": xxx,
  "expiration_date": {
    "$date": "XXXXXXXXXZ"
  },
  "serial_number": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "status": "xxx",
  "new field" <- see below for this
  
}
```

final model:
```
{
  "cluster_name": "cluster1",
  "csi_id": xxx,
  "namespace": "project1",
  "object_name": "deployment1",
  "certificates" [certificate model],
}
```


What I am trying to achieve is to aleert the support teams, hey look there is a service with an expiring cert coming soon and here are all the certs inside this service. Need less to say this needs to be performe very efficeiently, no room for error and fast as there many records. Pleae use better coding standards, and desgin patterns prven algoritms to acieve this. I will be running this daly as abtch so I need you to incorporate email alert to me if this batch fails. And a nice summay to be sent at the end of the day.

Is there any way we can perform a string compariuson or word closeness comparison to see if the "distinguished_name" matches (or closily resembles) inside the list so that we know there a possible chance that expiring cert is renewed? you know what I mean? and based on that result maybe add a new field to highlight this needs attention or something?

Provide me all the quired indexes I need to have for the source collection and targetr colleciton.



{
  "distinguished_name": "CN=rfa.afore.mexico.chase.net",
  "start_date": {
    "$date": "2025-05-15T01:03:33.000Z"
  },
  "expiration_date": {
    "$date": "2027-05-15T01:03:33.000Z"
  },
  "csi_application_id": 154958,
  "status": "Valid",
  "days_to_expiration": 436,
  "source_properties": {
    "name": "SSG",
    "serial_number": "690020648AD382F1E1E02AFD0F00000020648A",
    "certificate_type": "null",
    "certificate_owner": "null",
    "certificate_name": "null",
    "owner_email": "null",
    "support_group": "null",
    "support_group_email": "null",
    "application_manager": "null",
    "l3_application_head": "null",
    "l4_application_head": "null",
    "environment": "PROD",
    "evolven_host": "null",
    "evolven_path": "null",
    "ssg_domain": "sogateway.retail.chase.net",
    "ssg_url_in": "http://127.10.10.2:6238/afore-qaid/ApiACB/TOKEN",
    "ssg_url_out": "https://GCB-AforeBNMX-QAID-154958-LBG/ApiACB/TOKEN",
    "internal_ssg_domain": "RetailApplication",
    "ssg_url": "/afore-qaid/ApiACB/TOKEN",
    "san_names": "null",
    "instance_name": "NDR-GCB-AforeBNMX-Banxico-154958-ACL,NDR-GCB-AforeBNMX-Bloomberg-154958-ACL,NDR-GCB-AforeBNMX-QAID-154958-ACL,",
    "microservice_name": "GCB-AforeBNMX-QAID-154958",
    "openshift_namespace": "null",
    "openshift_container": "null",
    "ssl_cm_region": "LATM",
    "ssl_cm_sector": "LF-MEX",
    "ssl_cm_status": "null",
    "lob_domain": "",
    "TechnologyManagedSegment_L6": "LF - Other Retail Banking [L6]",
    "TechnologyManagedSegment_L7": "LF - PBWM O&T and Fraud [L7]",
    "ApplicationManager": "",
    "ApplicationManager_soeid": "",
    "Level3Head": "",
    "Level4Head": "",
    "Level5Head": "",
    "SupportManager": "",
    "Domain": "",
    "SubDomain": "",
    "LOB": ""
  },
  "log_date": {
    "$date": "2026-03-04T17:42:16.618Z"
  }
}