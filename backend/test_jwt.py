from datetime import datetime, timedelta
from jose import jwt, JWTError

payload = {
    "sub": "123",
    "email": "test@test.com",
    "iat": datetime.utcnow().isoformat(),
    "exp": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    "scope": "analyze",
}

secret = "supersecretkey"

try:
    token = jwt.encode(payload, secret, algorithm="HS256")
    print("Encoded token successfully.")
    
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    print("Decoded token successfully:", decoded)
except Exception as e:
    print("Failed with error:", type(e), e)
