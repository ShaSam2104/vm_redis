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

 
    def set_value(self, user_id, key, value, value_type=None, expiry=None):
        data = {
            "key": key,
            "value": value,
            "type": value_type
        }
        if expiry:
            data["expiry"] = expiry
        response = requests.post(f"{self.base_url}/user/{user_id}/set", json=data)
        print(response.json())
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

# # Create client instance
# client = KeyValueClient(host="127.0.0.1", port=8000)

# # Use the client functions
# result = client.set_value("user1", "mykey", "myvalue")
# value = client.get_value("user1", "mykey")
# keys = client.get_keys("user1")