"""
Valve CD Key Decoder/Encoder

Decodes and encodes 25-character Valve CD keys to extract/encode:
- GameCode (7 bits, 0-127): Identifies the game/application
- SalesTerritoryCode (8 bits, 0-255): Region/territory code
- SerialNumber (25 bits, 0-33554431): Batch/serial identifier

Format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX (25 chars, 5 groups of 5)

Based on reverse engineering work by billysb, cystface_man, and others.
"""
import random
from typing import List, Optional, Tuple, NamedTuple

# Character set for encoding (base-32 variant)
CODON_TO_ASCII = "ABCDEFGHIJKLMN2PQRST3VWXYZ456789"

# Default obfuscation table
DEFAULT_COBF_TABLE = [0xDC, 0x54, 0xE2, 0x08, 0x6B, 0x9C, 0xED, 0xF9, 0xDA]


class CDKeyInfo(NamedTuple):
    """Decoded CD key information."""
    game_code: int          # 7-bit game identifier (0-127)
    territory_code: int     # 8-bit region/territory code (0-255)
    serial_number: int      # 25-bit serial/batch number
    is_valid: bool          # Whether the key passed checksum validation


def _bits_to_bytes(bits: List[int]) -> List[int]:
    """Pack bits (length must be multiple of 8) into bytes."""
    result = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if bits[i + j]:
                byte |= 1 << (7 - j)
        result.append(byte)
    return result


def _checksum5(bits120: List[int]) -> List[int]:
    """Compute 8-bit sum & mask to 5 bits, return as list of 5 bits (MSB first)."""
    s = sum(_bits_to_bytes(bits120)) & 0xFF
    ck = s & 0x1F
    return [(ck >> i) & 1 for i in (4, 3, 2, 1, 0)]


def decode_cdkey(
    cdkey: str,
    cobf_table: Optional[List[int]] = None
) -> Optional[CDKeyInfo]:
    """
    Decode a 25-character Valve CD key.

    Args:
        cdkey: The CD key string (with or without hyphens)
        cobf_table: Optional custom obfuscation table (9 bytes)

    Returns:
        CDKeyInfo with decoded fields, or None if key format is invalid
    """
    if cobf_table is None:
        cobf_table = DEFAULT_COBF_TABLE

    # Normalize key: remove hyphens and uppercase
    cdkey = cdkey.replace("-", "").replace(" ", "").upper()

    if len(cdkey) != 25:
        return None

    # Convert characters to bits
    bitstring = []
    for ch in cdkey:
        idx = CODON_TO_ASCII.find(ch)
        if idx == -1:
            return None  # Invalid character
        bits = [(idx >> i) & 1 for i in (4, 3, 2, 1, 0)]
        bitstring.extend(bits)

    # Extract components
    obf = bitstring[:40]
    filler = bitstring[40:120]
    checksum = bitstring[120:]

    # Validate checksum
    expected = _checksum5(obf + filler)
    is_valid = (checksum == expected)

    # De-obfuscate payload
    payload = []
    for i in range(40):
        tbl_byte = cobf_table[i // 8]
        tbl_bit = (tbl_byte >> (7 - (i % 8))) & 1
        payload.append(obf[i] ^ tbl_bit)

    # Extract fields from payload
    game_code = int(''.join(map(str, payload[0:7])), 2)       # 7 bits
    territory_code = int(''.join(map(str, payload[7:15])), 2)  # 8 bits
    serial_number = int(''.join(map(str, payload[15:40])), 2)  # 25 bits

    return CDKeyInfo(
        game_code=game_code,
        territory_code=territory_code,
        serial_number=serial_number,
        is_valid=is_valid
    )


def encode_cdkey(
    game_code: int,
    territory_code: int,
    serial_number: int,
    cobf_table: Optional[List[int]] = None,
    filler: Optional[List[int]] = None,
    random_filler: bool = True
) -> str:
    """
    Generate a 25-character Valve CD key.

    Args:
        game_code: 7-bit game identifier (0-127)
        territory_code: 8-bit territory code (0-255)
        serial_number: 25-bit serial number (0-33554431)
        cobf_table: Optional custom obfuscation table (9 bytes)
        filler: Optional explicit list of 80 bits for middle section
        random_filler: If True and filler is None, use random bits

    Returns:
        Formatted CD key string (XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)

    Raises:
        ValueError: If field values are out of valid range
    """
    if cobf_table is None:
        cobf_table = DEFAULT_COBF_TABLE

    # Validate ranges
    if not (0 <= game_code <= 127):
        raise ValueError(f"game_code must be 0-127, got {game_code}")
    if not (0 <= territory_code <= 255):
        raise ValueError(f"territory_code must be 0-255, got {territory_code}")
    if not (0 <= serial_number <= 0x1FFFFFF):
        raise ValueError(f"serial_number must be 0-33554431, got {serial_number}")

    # Pack payload bits
    payload = []
    for shift in range(6, -1, -1):
        payload.append((game_code >> shift) & 1)
    for shift in range(7, -1, -1):
        payload.append((territory_code >> shift) & 1)
    for shift in range(24, -1, -1):
        payload.append((serial_number >> shift) & 1)

    # Obfuscate first 40 bits
    obf = []
    for i in range(40):
        tbl_byte = cobf_table[i // 8]
        tbl_bit = (tbl_byte >> (7 - (i % 8))) & 1
        obf.append(payload[i] ^ tbl_bit)

    # Filler bits (bits 40-119)
    if filler is not None:
        if len(filler) != 80:
            raise ValueError("filler must be exactly 80 bits")
        mid = filler
    elif random_filler:
        mid = [random.getrandbits(1) for _ in range(80)]
    else:
        mid = [0] * 80

    # Compute checksum over 120 bits
    first120 = obf + mid
    chk_bits = _checksum5(first120)

    # Final bitstream: 125 bits
    full_bits = first120 + chk_bits

    # Convert to characters
    chars = []
    for i in range(0, 125, 5):
        idx = 0
        for b in full_bits[i:i + 5]:
            idx = (idx << 1) | b
        chars.append(CODON_TO_ASCII[idx])

    # Format with hyphens
    groups = [''.join(chars[i:i + 5]) for i in range(0, 25, 5)]
    return '-'.join(groups)


def validate_cdkey_format(cdkey: str) -> bool:
    """
    Check if a string is a valid Valve CD key format.

    Args:
        cdkey: The key string to validate

    Returns:
        True if the key has valid format and checksum
    """
    info = decode_cdkey(cdkey)
    return info is not None and info.is_valid


# Territory code constants (common values)
class SalesTerritory:
    """Common sales territory codes."""
    WORLDWIDE = 0
    USA = 1
    EUROPE = 2
    ASIA = 3
    AUSTRALIA = 4
    LATIN_AMERICA = 5
    # Add more as needed based on Valve's actual territory mapping


if __name__ == "__main__":
    # Test encoding and decoding
    game = 0       # game code
    region = 5     # region/territory
    serial = 1337  # serial number

    key = encode_cdkey(game, region, serial)
    print(f"Generated key: {key}")

    decoded = decode_cdkey(key)
    if decoded:
        print(f"Decoded: game={decoded.game_code}, territory={decoded.territory_code}, "
              f"serial={decoded.serial_number}, valid={decoded.is_valid}")
