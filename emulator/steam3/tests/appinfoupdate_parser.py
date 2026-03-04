import struct

def main():
    # Hardcoded values
    client_address = "127.0.0.1"
    
    # Example hardcoded byte string (equivalent to: last_change_number=1, send_change_list=True)
    data_bytes = b'b\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\xc9\x13\x14\x00\x00\x00\x00\x00\x01'

    # Unpack the byte string using the format: little-endian int (4 bytes) and a boolean (1 byte)
    try:
        last_change_number, send_change_list = struct.unpack_from("<i?", data_bytes[16:], 0)
    except struct.error as e:
        print(f"Error unpacking data: {e}")
        return

    # Print the extracted information
    print(f"{client_address} [handle_ClientAppInfoupdate] last change number: {last_change_number}, send change list: {send_change_list}")

if __name__ == "__main__":
    main()