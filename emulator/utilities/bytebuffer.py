class ByteBuffer(object):
    def __init__(self, data, position=0, fromEnd=False):
        self.position = None
        self.data = data
        self.seekAbsolute(position, fromEnd)
        self.posDict = {}
        self.lastidx = 0

    def read(self, amount):
        if amount >= 0:
            data = self.data[self.position:self.position + amount]
        else:
            start = self.position + amount
            if start < 0:
                start = 0
            data = self.data[start:self.position]
        self.position += amount
        self._limitPosition()
        return data

    def read_8u(self):
        self.read(1)

    def read_16u(self):
        self.read(2)

    def read_32u(self):
        self.read(4)

    def read_64u(self):
        self.read(8)

    def read_string(self):
        null_byte_position = self.data.find(b'\x00', self.position)
        if null_byte_position == -1:
            print("[ByteBuffer] Error! No null terminations found!")
            return
        string_data = self.read(null_byte_position - self.position)
        # Move the cursor after the null byte (if found)
        if null_byte_position != -1:
            self.seekAbsolute(null_byte_position + 1)
        return string_data
        
    def readDelim(self, char, skipChar=False):
        target = self.data.index(char, self.position)
        data = self.read(target - self.position)
        if skipChar:
            self.seekRelative(len(char))
        return data

    def read_remaining(self):
        remaining_data = self.read(len(self.data) - self.position)
        return remaining_data

    def seekRelative(self, amount):
        self.position += amount
        self._limitPosition()

    def seekAbsolute(self, position, fromEnd=False):
        if fromEnd:
            self.position = len(self.data) - position
        else:
            self.position = position
        self._limitPosition()

    def _limitPosition(self):
        if self.position < 0:
            self.position = 0
        elif self.position > len(self.data):
            self.position = len(self.data)

    def save(self, idx):
        self.posDict[idx] = self.position
        self.lastidx = idx

    def load(self, idx):
        if self.lastidx == idx:
            return

        self.save(self.lastidx)
        self.lastidx = idx

        if idx in self.posDict:
            self.position = self.posDict[idx]
        else:
            self.position = 0

    def index(self):
        return self.position

    def eof(self):
        return self.position == len(self.data)