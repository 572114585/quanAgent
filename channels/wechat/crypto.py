"""CDN 加密/解密工具"""
import base64
import os

from Crypto.Cipher import AES


def generate_aes_key() -> bytes:
    """生成 16 字节 AES-128 密钥"""
    return os.urandom(16)


def aes_key_hex(key: bytes) -> str:
    """AES 密钥 → hex 字符串"""
    return key.hex()


def aes_key_base64(key: bytes) -> str:
    """AES 密钥 → base64 字符串"""
    return base64.b64encode(key).decode("ascii")


def aes_ecb_padded_size(size: int) -> int:
    """AES-ECB 填充后的大小"""
    block = 16
    return ((size + block - 1) // block) * block


def encrypt_aes_ecb(key: bytes, plaintext: bytes) -> bytes:
    """AES-128-ECB 加密（无 IV）"""
    cipher = AES.new(key, AES.MODE_ECB)
    # PKCS7 填充
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)
    return cipher.encrypt(padded)


def decrypt_aes_ecb(key: bytes, ciphertext: bytes) -> bytes:
    """AES-128-ECB 解密（PKCS7 去填充，含校验）

    安全：校验密文长度对齐、pad_len 范围、尾部填充字节一致，
    避免恶意/损坏密文导致数据截断或返回空。
    """
    if len(ciphertext) == 0 or len(ciphertext) % 16 != 0:
        raise ValueError("ciphertext length must be a positive multiple of 16")
    cipher = AES.new(key, AES.MODE_ECB)
    padded = cipher.decrypt(ciphertext)
    # PKCS7 去填充（手动校验，等价于 Crypto.Util.Padding.unpad）
    pad_len = padded[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError(f"invalid PKCS7 padding length: {pad_len}")
    # 校验尾部 pad_len 个字节都等于 pad_len，防伪造填充
    if padded[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("invalid PKCS7 padding bytes")
    return padded[:-pad_len]


def decode_aes_key(aes_key_base64: str) -> bytes:
    """
    解码 AES 密钥，兼容两种格式：
    1. base64-of-raw-16-bytes（16 原始字节 base64 编码）
    2. base64-of-hex-string（32 hex 字符 base64 编码）
    """
    raw = base64.b64decode(aes_key_base64)
    if len(raw) == 16:
        return raw
    # base64-of-hex-string：解码后是 hex 字符串
    hex_str = raw.decode("utf-8")
    return bytes.fromhex(hex_str)
