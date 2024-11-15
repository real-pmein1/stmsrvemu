class SizePrefixedInputStream:
    def __init__(self, input_stream, endianess='little'):
        """
        Initializes the SizePrefixedInputStream instance.

        :param input_stream: The underlying input stream to read from.
        :param endianess: Byte order ('little' or 'big').
        """
        self.input_stream = input_stream
        self.endianess = endianess
        self.size = self.read_stream_size(input_stream, endianess)
        self.remaining_size = self.size

    def read(self, length):
        """
        Reads up to 'length' bytes from the stream.

        :param length: Number of bytes to read.
        :return: Bytes read from the stream.
        """
        if self.remaining_size <= 0:
            raise EOFError("No more data to read from the stream")

        # Ensure not to read beyond the available data size
        length_to_read = min(length, self.remaining_size)
        data = self.input_stream.read(length_to_read)
        actual_read = len(data)

        if actual_read != length_to_read:
            raise IOError("Could not read the requested number of bytes")

        self.remaining_size -= actual_read
        return data

    @staticmethod
    def read_stream_size(input_stream, endianess):
        """
        Reads the size of the stream from the input.

        :param input_stream: The input stream to read from.
        :param endianess: Byte order ('little' or 'big').
        :return: Size of the stream.
        """
        size_bytes = input_stream.read(4)  # Assuming SizeType is 4 bytes (32-bit integer)
        if len(size_bytes) != 4:
            raise ValueError("Not enough data to read stream size")

        # Convert bytes to integer based on the endianess
        size = int.from_bytes(size_bytes, endianess)
        return size

    def __repr__(self):
        """Returns a string representation of the object with all attributes."""
        return (
            f"SizePrefixedInputStream("
            f"input_stream={self.input_stream}, "
            f"endianess='{self.endianess}', "
            f"size={self.size}, "
            f"remaining_size={self.remaining_size})"
        )