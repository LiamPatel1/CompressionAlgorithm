import hashlib
import os
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt(plaintext, password):

    padding = 0
    while len(plaintext) % 16 != 0:      # ensures the plaintext is a multiple of 16 bytes, and stores by how much
        plaintext += b'0'
        padding += 1
    plaintext = padding.to_bytes(16, byteorder=sys.byteorder) + plaintext

    key = hashlib.sha256(password.encode()).digest()  # returns 32 byte hash of password
    iv = os.urandom(16)  # initialisation vector (random data to stop identical files returning the same ciphertext)

    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()  # cipher text
    return iv + ciphertext  # prepends iv to the ciphertext


def decrypt(ciphertext, password):

    key = hashlib.sha256(password.encode()).digest()
    iv = ciphertext[:16]

    ciphertext = ciphertext[16:]

    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()  # decrypts ciphertext
    padding = int.from_bytes(plaintext[:16], byteorder=sys.byteorder)
    plaintext = plaintext[16:]
    plaintext = plaintext[:len(plaintext)-padding]   # removes padding

    return plaintext
