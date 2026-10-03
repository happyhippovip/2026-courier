import secrets
import os

class TokenManager:
    """WK-08: Verify controller.token creation, storage, access, health authentication."""
    def __init__(self, token_path: str):
        self.token_path = token_path

    def generate_and_store(self) -> str:
        token = secrets.token_hex(32)
        with open(self.token_path, 'w') as f:
            f.write(token)
        os.chmod(self.token_path, 0o600)  # Secure storage
        return token

    def read_token(self) -> str:
        if not os.path.exists(self.token_path):
            raise FileNotFoundError("Token file missing.")
        with open(self.token_path, 'r') as f:
            return f.read().strip()

    def verify_request(self, auth_header: str) -> bool:
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
        provided = auth_header.split(" ")[1]
        try:
            expected = self.read_token()
            return secrets.compare_digest(provided, expected)
        except FileNotFoundError:
            return False
