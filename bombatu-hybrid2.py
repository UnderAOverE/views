{
  "controller": {
    "name": "p14",
    "environment": "production",
    "enable": true,
    "url": "https://appdync-nam-gcp-p14.cloudsql.com:8090",
    "account": "customer1",
    "oauth2": {
      "method": "POST",
      "headers": {
        "Content-Type": "application/vnd.appd.ctrl+protobuf"
      },
      "path": "/controller/api/oauth/access_token",
      "login_details": {
        "aichatcore": {
          "secret_key": "***REDACTED***",
          "secret_token": "***REDACTED***",
          "bearer_token": "***REDACTED***",
          "bearer_token_expiration": {
            "$date": "2026-04-15T00:00:31.821Z"
          }
        },
        "aichat": {
          "secret_key": "***REDACTED***",
          "secret_token": "***REDACTED***",
          "bearer_token": "***REDACTED***",
          "bearer_token_expiration": {
            "$date": "2026-04-15T00:00:31.393Z"
          }
        },
        "aichat_qa": {
          "secret_key": "***REDACTED***",
          "secret_token": "***REDACTED***",
          "bearer_token": "***REDACTED***",
          "bearer_token_expiration": {
            "$date": "2026-04-15T00:00:32.265Z"
          }
        }
      }
    },
    "method": "GET",
    "https": {
      "ca_certs": "lib/ca-prod.pem",
      "enable": true
    },
    "timeout": 60,
    "params": {
      "output": "json"
    }
  }
}