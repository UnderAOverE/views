Here I have 5 million records inside my source collection (Certificates) like below:
'''
"cn","US","See2a6c9f6542a4736ffb76516bfe3",7,2026-03-09T00:00:00.000000+0000,170644,Activated,SSL Tracker,null,null,null,null,null,null,null,null
"cn","US","See2a6c9f6542a4736ffb76516bfe3",7,2026-03-09T00:00:00.000000+0000,178961,null,HashiCorp,namgcbgtd42p_gcb-nam-iam-ccp-178961_gtlecsprod-xlg-sct-p-sts-ob-canary,null,null,null,null,null,N/A,null
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
