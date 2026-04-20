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

