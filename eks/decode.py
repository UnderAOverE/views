import base64

def decode_eks_token(eks_token: str) -> str:
    """
    Decodes the payload of an AWS EKS bearer token to reveal the pre-signed STS URL.
    
    EKS tokens have the format: k8s-aws-v1.<Base64URL_Payload>
    """
    PREFIX = "k8s-aws-v1."
    
    if not eks_token.startswith(PREFIX):
        return f"Error: Token does not start with the required EKS prefix '{PREFIX}'."

    # 1. Strip the prefix
    base64_payload = eks_token[len(PREFIX):]
    
    # Base64 URL-safe decoding requires padding. If the original string had
    # padding removed (which is common), we must add it back manually.
    # The length must be a multiple of 4.
    padding_needed = len(base64_payload) % 4
    if padding_needed != 0:
        base64_payload += '=' * (4 - padding_needed)

    try:
        # 2. Decode the payload
        decoded_bytes = base64.urlsafe_b64decode(base64_payload.encode('utf-8'))
        decoded_url = decoded_bytes.decode('utf-8')
        
        return decoded_url
        
    except Exception as e:
        return f"Error during Base64 decoding: {e}"

# --- Example Usage ---

# NOTE: This is a truncated, fictional example token for demonstration. 
# A real token would be much longer.
example_token = (
    "k8s-aws-v1.aHR0cHM6Ly9zdHMuYXAtc291dGhlYXN0LTIuYW1hem9uYXdzLmNvbS8"
    "yQWN0aW9uPUdldENhbGxlcklkZW50aXR5JlZlcnNpb249MjAxMS0wNi0xNSZYLUFtei"
    "1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUExT"
    "DJaVzFGTkNYVUpQRFYlMkYyMDI1MTAwM0dldENhbGxlcklkZW50aXR5"
)

decoded_result = decode_eks_token(example_token)

print(f"Original Token: {example_token[:50]}...")
print("\n--- DECODED PAYLOAD (Pre-signed STS URL) ---")
print(decoded_result)
