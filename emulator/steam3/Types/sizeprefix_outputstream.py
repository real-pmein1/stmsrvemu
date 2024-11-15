class SizePrefixedOutputStream:
    def __init__(self, output_stream, size_type=None, endianess='little'):
        """
        Initializes the SizePrefixedOutputStream instance.

        :param output_stream: The underlying output stream to write to.
        :param size_type: Optional size for the buffer (used if provided).
        :param endianess: Byte order ('little' or 'big').
        """
        self.output_stream = output_stream
        self.endianess = endianess
        self.buffer_stream = ByteArrayOutputStream(size_type) if size_type is not None else ByteArrayOutputStream()

    def __del__(self):
        """Destructor to ensure the stream is closed when the object is deleted."""
        self.close()

    def close(self):
        """
        Closes the buffer stream, flushes data to the underlying output stream, and writes the size-prefixed data.
        """
        if self.buffer_stream:
            try:
                self.flush()
                size = len(self.buffer_stream)
                size_bytes = size.to_bytes((size.bit_length() + 7) // 8, self.endianess)
                self.output_stream.write(size_bytes)
                self.output_stream.write(self.buffer_stream.get_bytes())

                self.buffer_stream = None  # Clear the buffer stream
            except Exception as e:
                self.buffer_stream = None
                raise e

    def flush(self):
        """Flushes the buffer stream."""
        if self.buffer_stream:
            self.buffer_stream.flush()

    def write(self, data):
        """
        Writes data to the buffer stream.

        :param data: Byte data to write to the stream.
        """
        if self.buffer_stream:
            self.buffer_stream.write(data)

    def is_seekable(self):
        """
        Checks if the buffer stream is seekable.

        :return: True if seekable, False otherwise.
        """
        return self.buffer_stream.is_seekable() if self.buffer_stream else False

    def get_position(self):
        """
        Gets the current position in the buffer stream.

        :return: The current position, or 0 if the buffer stream is not available.
        """
        return self.buffer_stream.get_position() if self.buffer_stream else 0

    def set_position(self, offset, origin):
        """
        Sets the position in the buffer stream.

        :param offset: The position offset.
        :param origin: The origin from where to seek.
        :return: The new position.
        """
        return self.buffer_stream.set_position(offset, origin) if self.buffer_stream else 0

    def __repr__(self):
        """Returns a string representation of the object with all attributes."""
        return (
            f"SizePrefixedOutputStream("
            f"output_stream={self.output_stream}, "
            f"endianess='{self.endianess}', "
            f"buffer_stream={self.buffer_stream})"
        )

class ByteArrayOutputStream:
    def __init__(self, size=None):
        """Initializes a ByteArrayOutputStream."""
        self.buffer = bytearray() if size is None else bytearray(size)

    def flush(self):
        """Flushes the buffer (no-op for in-memory buffer)."""
        pass

    def write(self, data):
        """Writes data to the in-memory buffer."""
        self.buffer.extend(data)

    def get_bytes(self):
        """Returns the contents of the buffer as bytes."""
        return bytes(self.buffer)

    def __len__(self):
        """Returns the size of the buffer."""
        return len(self.buffer)

    def is_seekable(self):
        """Returns True because an in-memory buffer is seekable."""
        return True

    def get_position(self):
        """Returns the current position (end of buffer)."""
        return len(self.buffer)

    def set_position(self, offset, origin):
        """Sets the position in the buffer (simplified)."""
        if origin == 0:  # Absolute
            new_position = offset
        elif origin == 1:  # Relative to current
            new_position = len(self.buffer) + offset
        elif origin == 2:  # Relative to end
            new_position = len(self.buffer) - offset
        else:
            raise ValueError("Invalid origin for set_position")
        return new_position