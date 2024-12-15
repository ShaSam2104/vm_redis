import sys
import requests
import os
import json
import hashlib
import ecdsa
from pathlib import Path
BASE_URL = "http://10.20.24.88:8000"
VM_URL = "http://127.0.0.1:8000"
CREDENTIALS_FILE = Path.home() / ".cache" / "credentials.json"

class AuthClient:
    def __init__(self):
        self.base_url = BASE_URL
        self.credentials = self.load_credentials()
        self.ensure_auth()
        if self.credentials:
            self.base_url = f"http://{self.credentials['vm_ip']}:8000"
    
    def load_credentials(self):
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE) as f:
                return json.load(f)
        return None
    
    def save_credentials(self, creds):
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(creds, f)
        self.credentials = creds
    
    def ensure_auth(self):
        if not self.credentials:
            self.handle_signup()
    
    def generate_keypair(self, passphrase):
        signing_key = ecdsa.SigningKey.from_string(
            hashlib.sha256(passphrase.encode("utf-8")).hexdigest()[:24].encode("utf-8")
        )
        verifying_key = signing_key.get_verifying_key()
        return {
            'private_key': signing_key.to_string().hex(),
            'public_key': verifying_key.to_string().hex(),
            'passphrase': passphrase
        }
    def handle_signup(self):
        passphrase = input("Enter passphrase for signup: ")
        keypair = self.generate_keypair(passphrase)
        
        response = requests.post(f"{BASE_URL}/signup", json={
            "public_key": keypair['public_key']
        })
        
        if response.status_code == 200:
            creds = {**keypair, 'vm_ip': response.json()['vm_ip']}
            self.save_credentials(creds)
            self.base_url = f"http://{creds['vm_ip']}:8000"
            print("Signup successful!")
        else:
            print("Signup failed:", response.json())
            sys.exit(1)
    
    def sign_request(self, body):
        # Generate salt from request body
        salt = hashlib.sha256(str(body).encode("utf-8")).hexdigest().encode("utf-8")
        
        # Sign using private key
        signing_key = ecdsa.SigningKey.from_string(
            bytes.fromhex(self.credentials['private_key'])
        )
        signature = signing_key.sign(salt.encode()).hex()
        
        return {
            "public_key": self.credentials['public_key'],
            "salt": salt,
            "signature": signature
        }
    def authenticated_request(self, method, url, **kwargs):
        # Replace BASE_URL with VM URL for all authenticated requests
        url = url.replace(BASE_URL, self.base_url)
        
        body = kwargs.get('json', kwargs.get('data', ''))
        auth_headers = self.sign_request(body)
        
        headers = kwargs.pop('headers', {})
        headers.update(auth_headers)
        kwargs['headers'] = headers
        
        return requests.request(method, url, **kwargs)
def ping(client):
    response = client.authenticated_request(
        'POST',
        f"{BASE_URL}/user/{client.credentials['public_key']}/ping"
    )
    print(response.json())

def echo(client, message):
    response = client.authenticated_request(
        'POST', 
        f"{BASE_URL}/user/{client.credentials['public_key']}/echo",
        params={"message": message}
    )
    print(response.json())

def set_value(client, key, value,type=None, expiry=None):
    data = {"key": key, "value": value, "type": type}
    if expiry:
        data["expiry"] = expiry
        response = client.authenticated_request(
        'POST', 
        f"{BASE_URL}/user/{client.credentials['public_key']}/set", 
        json=data)
    print(response.json())

def set_file(client, key, file_path, expiry=None):
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    try:
        files = {"file": open(file_path, "rb")}
        data = {"key": key}
        if expiry:
            data["expiry"] = expiry
        
        response = requests.post(f"{BASE_URL}/user/{client.credentials['public_key']}/setfile", files=files, data=data)
        if response.status_code == 200:
            print(response.json())
        else:
            print(f"Error: {response.json()['detail']}")
    except requests.exceptions.RequestException as e:
        print(f"Network error: {str(e)}")
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
    finally:
        if 'files' in locals():
            files["file"].close()

def get_file(client, key, save_path):
    response = requests.get(f"{BASE_URL}/user/{client.credentials['public_key']}/getfile", params={"key": key})
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(f"File saved to {save_path}")
    else:
        print(f"Error: {response.json()}")
def get_value(client, key):
    response = client.authenticated_request('GET', f"{BASE_URL}/user/{client.credentials['public_key']}/get", params={"key": key})
    print(response.json())

def get_keys(client):
    response = client.authenticated_request('GET', f"{BASE_URL}/user/{client.credentials['public_key']}/keys")
    print(response.json())

def get_info(client):
    response = client.authenticated_request('GET', f"{BASE_URL}/info")
    print(response.json())

def delete_key(client, key):
    response = client.authenticated_request('DELETE', f"{BASE_URL}/user/{client.credentials['public_key']}/key/{key}")
    print(response.json())

def delete_user(client):
    response = client.authenticated_request('DELETE', f"{BASE_URL}/user/{client.credentials['public_key']}")
    print(response.json())
def download_rdb(client, save_path=None):
    url = f"{BASE_URL}/download_rdb/{client.credentials['public_key']}"
    params = {"path": save_path} if save_path else {}
    response = requests.get(url, params=params, stream=True)
    
    if save_path:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"RDB file saved to {save_path}")
    else:
        save_path = f"{client.credentials['public_key'] or 'all_users'}_dump.rdb"
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"RDB file saved to {save_path}")

def upload_rdb(client,file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    files = {"file": open(file_path, "rb")}
    url = f"{BASE_URL}/upload_rdb"
    try:
        response = requests.post(url, files=files)
        print(response.json())
    except Exception as e:
        print(f"Error uploading RDB file: {str(e)}")
    finally:
        files["file"].close()

def get_storage_usage(client):
    response = client.authenticated_request('GET', f"{BASE_URL}/user/{client.credentials['public_key']}/usage")
    if response.status_code == 200:
        data = response.json()
        print(f"Storage used: {data['storage_used']/1024/1024:.2f}MB")
        print(f"Storage limit: {data['storage_limit']/1024/1024:.2f}MB")
        print(f"Subscription tier: {data['subscription']}")
    else:
        print(f"Error: {response.text}")

def update_subscription(client, tier):
    response = client.authenticated_request(
        'POST',
        f"{BASE_URL}/user/{client.credentials['public_key']}/subscription",
        params={"tier": tier}
    )
    print(response.json())
def main():
    # Command examples in help text
    help_text = """
    Available commands:
    - ping
    - echo <message>
    - set <key> <value> [expiry]
    - setfile <key> <file_path> [expiry]
    - getfile <key> <save_path>
    - get <key>
    - keys 
    - info
    - config <command> <value>
    - psync <replica_id> <offset>
    - users
    - download_rdb [user_id] [save_path]
    - upload_rdb <file_path> [user_id]
    - help
    - exit
    - delete_key <key>
    - delete_user 
    - delete_users
    - usage             # Get storage usage stats
    - upgrade <tier>   # Change subscription tier (basic/premium)   
    Examples:
    > ping user1
    > echo user1 hello
    > set user1 mykey myvalue 60
    > setfile user1 myfile /path/to/file.pdf 3600
    > getfile user1 myfile /path/to/save/downloaded.pdf
    > get user1 mykey
    > keys user1
    """
    client = AuthClient()
    while True:
        command = input("Enter command: ").strip().split()
        if not command:
            continue
        
        cmd = command[0].lower()
        
        try:
            if cmd == "help":
                print(help_text)
            elif cmd == "ping":
                ping(client)
            elif cmd == "echo" and len(command) == 3:
                echo(client, command[1], command[2])
            elif cmd == "set" and len(command) >= 3:
                expiry = None
                type = None
                if len(command) >= 4 and command[3].isdigit():
                    expiry = int(command[3])
                if len(command) >= 5:
                    type = command[4]
                set_value(client, command[1], command[2], type, expiry)
            elif cmd == "setfile" and len(command) in [3, 4]:
                expiry = int(command[4]) if len(command) == 4 else None
                set_file(client.credentials['public_key'], command[2], command[3], expiry)
            elif cmd == "getfile" and len(command) == 3:
                get_file(client.credentials['public_key'], command[1], command[2])
            elif cmd == "get" and len(command) == 2:
                get_value(client, command[1])
            elif cmd == "keys" and len(command) == 1:
                get_keys(client)
            elif cmd == "info":
                get_info(client)
            elif cmd == "download_rdb":
                download_rdb(client, command[1] if len(command) >= 1 else None)
            elif cmd == "upload_rdb" and len(command) in [1, 2]:
                upload_rdb(client, command[1])
            elif cmd == "exit":
                break
            elif cmd == "delete_key" and len(command) == 2:
                delete_key(client, command[1])
            elif cmd == "delete_user" and len(command) == 1:
                delete_user(client)
            elif cmd == "usage" and len(command) == 1:
                get_storage_usage(client)
            elif cmd == "upgrade" and len(command) == 2:
                update_subscription(client, command[1])
            else:
                print("Invalid command. Type 'help' for usage.")
        except Exception as e:
            print(f"Error executing command: {str(e)}")

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 1:
        BASE_URL = f"http://{args[0]}:{args[1]}"
    main()
