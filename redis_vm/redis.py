import requests

class KeyValueClient:
    def __init__(self, host="127.0.0.1", port=8000):
        self.base_url = f"http://{host}:{port}"

    def ping(self, user_id):
        response = requests.post(f"{self.base_url}/user/{user_id}/ping")
        return response.json()

    def echo(self, user_id, message):
        response = requests.post(f"{self.base_url}/user/{user_id}/echo", params={"message": message})
        return response.json()

    def sign_up(self, user_id):
        response = requests.post(f"{self.base_url}/signup", json={"public_key": user_id})
        return response.json()

    def set_value(self, user_id, key, value, type=None, expiry=None):
        data = {"key": key, "value": value, "type": type}
        if expiry:
            data["expiry"] = expiry
        response = requests.post(f"{self.base_url}/user/{user_id}/set", json=data)
        return response.json()

    def get_value(self, user_id, key):
        response = requests.get(f"{self.base_url}/user/{user_id}/get", params={"key": key})
        return response.json()

    def get_keys(self, user_id):
        response = requests.get(f"{self.base_url}/user/{user_id}/keys")
        return response.json()

    def get_all_users(self):
        response = requests.get(f"{self.base_url}/users")
        return response.json()

    def delete_key(self, user_id: str, key: str):
        response = requests.delete(f"{self.base_url}/user/{user_id}/key/{key}")
        return response.json()

    def delete_user(self, user_id: str):
        response = requests.delete(f"{self.base_url}/user/{user_id}")
        return response.json()

    def delete_all_users(self):
        response = requests.delete(f"{self.base_url}/users")
        return response.json()

# how to use 
# from client_on_host import KeyValueClient

if __name__ == "__main__":

    # # Create client instance
    client = KeyValueClient(host="127.0.0.1", port=8000)

    # # Use the client functions
    result = client.set_value("user1", "mykey", [1, 2, 3, "bcd"], "list")
    value = client.get_value("user1", "mykey")
    keys = client.get_keys("user1")
    print(result, value)