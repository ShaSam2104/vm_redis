from ecdsa import SigningKey, VerifyingKey
import hashlib
import json

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
    return True

async def userExists(publickey):
    return True

async def retrieveSaltFromData(data):
    data0 = json.loads(data)
    return data0["salt"]