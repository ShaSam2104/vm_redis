from ecdsa import SigningKey, VerifyingKey
import hashlib
import json
from client_on_host import KeyValueClient

client = KeyValueClient()
async def generateKeyPair(password):
    hash0 = hashlib.sha256(password.encode("UTF-8")).hexdigest()[:24].encode("UTF-8")
    privkey = SigningKey.from_string(hash0)
    pubkey = privkey.get_verifying_key()
    return (privkey.to_string(), pubkey.to_string())

async def sign(password, message_dict):
    keys = generateKeyPair(password)
    hash0 = hashlib.sha256(message_dict.encode("UTF-8")).hexdigest().encode("UTF-8")
    privkey = SigningKey.from_string(keys[0])
    return privkey.sign(hash0)

# TODO decide on whether to have a hash or a public key be transferred every damn call
async def verifyRequest(publickey, sign, data):
    retval = False
    # ASSUMING that the data input is a str
    hash0 = hashlib.sha256(data.encode("UTF-8")).hexdigest().encode("UTF-8")
    salt = retrieveSaltFromData(data)
    if verifySalt(publickey, salt) and userExists(publickey):
        pubkey = VerifyingKey.from_string(publickey)
        retval = pubkey.verify(sign, hash0, hashfunc=None)
    else: 
        retval = False
    return retval

async def verifySalt(publickey, salt):
    try:
        response = client.get_value("host_vmm", "users")
        if "value" in response:
            users = response["value"]
            return users[publickey][salt] == salt
        return False
    except Exception as e:
        print(f"Error verifying salt: {e}")
        return False
    return True

async def ReplaceSalt(publickey, data):
    hash0 = hashlib.sha256(data.encode("UTF-8")).hexdigest().encode("UTF-8")
    try:
        response = client.get_value("host_vmm", "users")
        if "value" in response:
            users = response["value"]
            users[publickey]["salt"] = hash0
            client.set_value("host_vmm", "users", users)
        return "Salt replaced"
    except Exception as e:
        return f"Error replacing salt: {e}"

async def userExists(publickey):
    try:
        response = client.get_value("host_vmm", "users")
        if "value" in response:
            users = response["value"]
            return publickey in users        
        return False
    except Exception as e:
        print(f"Error checking user existence: {e}")
        return False

async def retrieveSaltFromData(data):
    data0 = json.loads(data)
    return data0["salt"]