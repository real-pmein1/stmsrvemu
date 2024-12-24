import os


def find_pattern(data, pattern):
    pattern_bytes = []
    wildcards = []

    for byte in pattern.split():
        if byte == '??':
            pattern_bytes.append(0x00)
            wildcards.append(True)
        elif '?' in byte:
            value = int(byte.replace('?', '0'), 16)  # Treat single digit wildcard as '0'
            pattern_bytes.append(value)
            wildcards.append(byte.count('?') == 1)  # True for single digit wildcard, False for exact match
        else:
            pattern_bytes.append(int(byte, 16))
            wildcards.append(False)

    for i in range(len(data) - len(pattern_bytes) + 1):
        if all((data[i + j] == pattern_bytes[j] or wildcards[j]) for j in range(len(pattern_bytes))):
            print(f"Pattern found at index: {i}")
            return i
    return -1


def patch_binary(data, offset, patch_bytes):
    return data[:offset] + patch_bytes + data[offset + len(patch_bytes):]


def find_and_replace_pattern(file, file_name, pattern, replacement, patch_loc_offset, standalone = False):
    # Convert the replacement to bytes
    replacement_bytes = bytes.fromhex(replacement)

    # figure out if any nops are needed:
    num_nops = abs(patch_loc_offset) - len(replacement_bytes)

    # Find the pattern
    pattern_offset = find_pattern(file, pattern)

    if pattern_offset != -1:
        # Calculate the offset to patch, which is 5 bytes before the pattern start
        patch_offset = pattern_offset + patch_loc_offset
        if patch_offset < 0:
            print(f"[{file_name}] Error: Pattern found too close to the start of the file for replacement.")
            return file

        # Apply the patchpatch_bytes = bytes.fromhex(replacement) + bytes([0x90] * num_nops)
        modified_bytes = patch_binary(file, patch_offset, replacement_bytes + bytes([0x90] * num_nops))

        # Save the modified file
        if standalone:
            modified_file_path = os.path.splitext(file_name)[0] + "_modified" + os.path.splitext(file_name)[1]
            with open(modified_file_path, "wb") as f:
                f.write(modified_bytes)
            print(f"[{file_name}] File successfully modified and saved as {modified_file_path}")

        return modified_bytes
    else:
        print(f"[{file_name}] Pattern not found.")
        return file


# standalone script usage
if __name__ == "__main__":
    dll_path = "steamui.dll"
    pattern = "83 c4 ?? 84 c0 75 08 83 c6 01"
    replacement = "B8 01 00 00 00"
    patch_location_offset = -5
    num_nops = abs(patch_location_offset) - len(bytes.fromhex("B8 01 00 00 00"))
    with open(dll_path, "rb") as f:
        file_bytes = f.read()

    browserfirneds_bytes = "83 C4 04 85 C0 74 02 B3"
    offset = 0
    replacement = "83 C4 04 85 C0 75 02 B3"
    find_and_replace_pattern(file_bytes, dll_path, pattern, replacement, patch_location_offset, True)