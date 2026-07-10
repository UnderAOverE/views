anomalies = st.Page(
    "pages/07_Anomalies.py",
    title="Anomalies",
    icon="🌪",
)

nav = st.navigation([
    home,
    targets,
    metrics_explorer,
    incidents,
    collections,
    config_inspector,
    thresholds_page,
    anomalies,          # <-- add here too, or it won't register
])


🚩


import json, base64, hashlib
from cryptography.hazmat.primitives import serialization
from cryptography import x509

def b64url(b):  # base64url, no padding
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def int_to_b64url(n):
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b64url(b)

# Load cert
with open("cert.pem", "rb") as f:
    cert = x509.load_pem_x509_certificate(f.read())

pub = cert.public_key()
numbers = pub.public_numbers()

# x5c = base64 (standard, WITH padding) of the DER cert, no PEM headers
der = cert.public_bytes(serialization.Encoding.DER)
x5c = base64.b64encode(der).decode()

# kid = SHA-1 thumbprint of the cert (common choice)
kid = hashlib.sha1(der).hexdigest()

jwk = {
    "kty": "RSA",
    "use": "sig",
    "kid": kid,
    "x5c": [x5c],
    "n": int_to_b64url(numbers.n),
    "e": int_to_b64url(numbers.e),
}

print(json.dumps({"keys": [jwk]}, indent=2))


# Extract the certificate (public part) from the p12
openssl pkcs12 -in yourfile.p12 -clcerts -nokeys -out cert.pem

# Extract the public key from the certificate
openssl x509 -in cert.pem -pubkey -noout > pubkey.pem



Key points

n and e must be base64url (not standard base64), no padding.
x5c must be standard base64 (with +// and = padding) of the DER bytes — this is the one exception to base64url in JWKS.
kid — vendors typically accept the cert SHA-1/SHA-256 thumbprint or any unique string; ask them if they expect a specific value.
Your example JSON has a bracket typo — x5c should be a closed array before n and e:

json{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "...",
      "x5c": ["MIID..."],
      "n": "...",
      "e": "AQAB"
    }
  ]
}


