"""Memory Vault — optional AES-256 encryption for memories.

When TESSERA_VAULT_KEY is set, memories are encrypted at rest.
All encryption happens locally — no cloud, no external services.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets

logger = logging.getLogger(__name__)

_vault_key: bytes | None = None


def init_vault() -> bool:
    """Initialize the vault from TESSERA_VAULT_KEY environment variable.

    Returns True if vault is enabled, False otherwise.
    """
    global _vault_key
    key_str = os.environ.get("TESSERA_VAULT_KEY", "")
    if not key_str:
        _vault_key = None
        return False

    # Derive a 32-byte key from the user's passphrase
    _vault_key = hashlib.sha256(key_str.encode("utf-8")).digest()
    logger.info("Vault enabled — memories will be encrypted at rest")
    return True


def is_vault_enabled() -> bool:
    """Check if the vault is currently enabled."""
    return _vault_key is not None


def encrypt(plaintext: str) -> str:
    """Encrypt text using AES-256-CBC.

    Returns base64-encoded string: iv(16 bytes) + ciphertext.
    Uses PKCS7 padding.

    Falls back to plaintext if vault is not enabled.
    """
    if _vault_key is None:
        return plaintext

    data = plaintext.encode("utf-8")

    # PKCS7 padding
    block_size = 16
    pad_len = block_size - (len(data) % block_size)
    data += bytes([pad_len]) * pad_len

    # Generate random IV
    iv = secrets.token_bytes(16)

    # AES-256-CBC encryption (pure Python implementation)
    ciphertext = _aes_cbc_encrypt(data, _vault_key, iv)

    # Encode as base64 with prefix
    encoded = base64.b64encode(iv + ciphertext).decode("ascii")
    return f"vault:{encoded}"


def decrypt(ciphertext: str) -> str:
    """Decrypt text encrypted with encrypt().

    Returns plaintext. If vault is not enabled or text is not encrypted,
    returns the input as-is.
    """
    if not ciphertext.startswith("vault:"):
        return ciphertext

    if _vault_key is None:
        logger.warning("Vault key not set but encrypted data found")
        return ciphertext  # Can't decrypt without key

    try:
        raw = base64.b64decode(ciphertext[6:])
        iv = raw[:16]
        data = raw[16:]

        plaintext_padded = _aes_cbc_decrypt(data, _vault_key, iv)

        # Remove PKCS7 padding
        pad_len = plaintext_padded[-1]
        if 1 <= pad_len <= 16:
            plaintext_padded = plaintext_padded[:-pad_len]

        return plaintext_padded.decode("utf-8")
    except Exception as e:
        logger.error("Decryption failed: %s", e)
        return ciphertext


def encrypt_dict(d: dict, fields: list[str] | None = None) -> dict:
    """Encrypt specified fields in a dictionary.

    Default fields: ["content"].
    """
    if not is_vault_enabled():
        return d

    fields = fields or ["content"]
    result = dict(d)
    for field in fields:
        if field in result and isinstance(result[field], str):
            result[field] = encrypt(result[field])
    return result


def decrypt_dict(d: dict, fields: list[str] | None = None) -> dict:
    """Decrypt specified fields in a dictionary.

    Default fields: ["content"].
    """
    fields = fields or ["content"]
    result = dict(d)
    for field in fields:
        if field in result and isinstance(result[field], str):
            result[field] = decrypt(result[field])
    return result


def vault_status() -> dict:
    """Get vault status information."""
    return {
        "enabled": is_vault_enabled(),
        "algorithm": "AES-256-CBC" if is_vault_enabled() else None,
        "key_source": "TESSERA_VAULT_KEY" if is_vault_enabled() else None,
    }


# ---------------------------------------------------------------------------
# Pure Python AES-256-CBC (no external dependencies)
# ---------------------------------------------------------------------------

# AES S-Box
_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i

_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _mix_single(a: int, b: int) -> int:
    """Galois field multiplication."""
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return p


def _key_expansion(key: bytes) -> list[list[int]]:
    """AES-256 key expansion → 15 round keys."""
    nk = 8  # 256-bit key
    nr = 14
    nb = 4

    w = []
    for i in range(nk):
        w.append(list(key[4 * i: 4 * i + 4]))

    for i in range(nk, nb * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        elif i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])

    # Group into round keys (4 words per round key)
    round_keys = []
    for r in range(nr + 1):
        rk = []
        for c in range(4):
            rk.append(w[r * 4 + c])
        round_keys.append(rk)
    return round_keys


def _add_round_key(state: list[list[int]], rk: list[list[int]]) -> None:
    for c in range(4):
        for r in range(4):
            state[r][c] ^= rk[c][r]


def _sub_bytes(state: list[list[int]]) -> None:
    for r in range(4):
        for c in range(4):
            state[r][c] = _SBOX[state[r][c]]


def _inv_sub_bytes(state: list[list[int]]) -> None:
    for r in range(4):
        for c in range(4):
            state[r][c] = _INV_SBOX[state[r][c]]


def _shift_rows(state: list[list[int]]) -> None:
    state[1] = state[1][1:] + state[1][:1]
    state[2] = state[2][2:] + state[2][:2]
    state[3] = state[3][3:] + state[3][:3]


def _inv_shift_rows(state: list[list[int]]) -> None:
    state[1] = state[1][-1:] + state[1][:-1]
    state[2] = state[2][-2:] + state[2][:-2]
    state[3] = state[3][-3:] + state[3][:-3]


def _mix_columns(state: list[list[int]]) -> None:
    for c in range(4):
        s = [state[r][c] for r in range(4)]
        state[0][c] = _xtime(s[0]) ^ (_xtime(s[1]) ^ s[1]) ^ s[2] ^ s[3]
        state[1][c] = s[0] ^ _xtime(s[1]) ^ (_xtime(s[2]) ^ s[2]) ^ s[3]
        state[2][c] = s[0] ^ s[1] ^ _xtime(s[2]) ^ (_xtime(s[3]) ^ s[3])
        state[3][c] = (_xtime(s[0]) ^ s[0]) ^ s[1] ^ s[2] ^ _xtime(s[3])


def _inv_mix_columns(state: list[list[int]]) -> None:
    for c in range(4):
        s = [state[r][c] for r in range(4)]
        state[0][c] = _mix_single(s[0], 14) ^ _mix_single(s[1], 11) ^ _mix_single(s[2], 13) ^ _mix_single(s[3], 9)
        state[1][c] = _mix_single(s[0], 9) ^ _mix_single(s[1], 14) ^ _mix_single(s[2], 11) ^ _mix_single(s[3], 13)
        state[2][c] = _mix_single(s[0], 13) ^ _mix_single(s[1], 9) ^ _mix_single(s[2], 14) ^ _mix_single(s[3], 11)
        state[3][c] = _mix_single(s[0], 11) ^ _mix_single(s[1], 13) ^ _mix_single(s[2], 9) ^ _mix_single(s[3], 14)


def _aes_encrypt_block(block: bytes, round_keys: list[list[list[int]]]) -> bytes:
    """Encrypt a single 16-byte block."""
    state = [[0] * 4 for _ in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] = block[c * 4 + r]

    _add_round_key(state, round_keys[0])

    for rnd in range(1, 14):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, round_keys[rnd])

    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, round_keys[14])

    result = bytearray(16)
    for r in range(4):
        for c in range(4):
            result[c * 4 + r] = state[r][c]
    return bytes(result)


def _aes_decrypt_block(block: bytes, round_keys: list[list[list[int]]]) -> bytes:
    """Decrypt a single 16-byte block."""
    state = [[0] * 4 for _ in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] = block[c * 4 + r]

    _add_round_key(state, round_keys[14])

    for rnd in range(13, 0, -1):
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, round_keys[rnd])
        _inv_mix_columns(state)

    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    _add_round_key(state, round_keys[0])

    result = bytearray(16)
    for r in range(4):
        for c in range(4):
            result[c * 4 + r] = state[r][c]
    return bytes(result)


def _aes_cbc_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-256-CBC encrypt. Data must be padded to 16-byte blocks."""
    round_keys = _key_expansion(key)
    prev = iv
    result = bytearray()

    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        xored = bytes(a ^ b for a, b in zip(block, prev))
        encrypted = _aes_encrypt_block(xored, round_keys)
        result.extend(encrypted)
        prev = encrypted

    return bytes(result)


def _aes_cbc_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-256-CBC decrypt."""
    round_keys = _key_expansion(key)
    prev = iv
    result = bytearray()

    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        decrypted = _aes_decrypt_block(block, round_keys)
        plaintext = bytes(a ^ b for a, b in zip(decrypted, prev))
        result.extend(plaintext)
        prev = block

    return bytes(result)
