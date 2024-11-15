import os
import struct
import zlib
from os import path
from pathlib import Path

import lzma

from blobreader import ReadBytes as ReadInfo

# // ------- Planning ------- //
#  - Group Compression.
#    - Chunks needed.
#    - File Format changes needed.
#  - Blob Extraction. Users must be able to extracted packed blobs.
#  - Preprocess firstblob UI and Steam versions?
#  - Better error handling of specific cases.

class FinalFileReaderv0(object):
   def __init__(self) -> None:
      print('Created File Format (110) object.')
      self.IsLoaded = False
      self.FirstData = {}
      self.SecondData = {}

      self.FirstHeaderSize = 0
      self.SecondHeaderSize = 0

      self.finalreader = None
      self.totalread = 0
   def Read(self, leng):
      return self.ReadBytes(leng) # Lazy way to do this
   def ReadBytes(self, leng):
      self.totalread = self.totalread + leng
      return self.finalreader.read(leng)
   def Load(self, file):
      self.finalreader = open(file, 'rb')
      HeaderID, FirstSize, SecondSize = struct.unpack('<ILL', self.ReadBytes(12))

      if HeaderID != 110:
         raise Exception("This is not a valid file format to read.")
         return

      self.FirstCount = struct.unpack('<I', self.Read(4))[0]

      # Read data.
      for i in range(self.FirstCount):
         filename_len = struct.unpack('<I', self.Read(4))[0]
         filename = self.Read(filename_len).decode('latin-1')
         filecrc, filedate, datapos, datalen = struct.unpack('<ILII', self.Read(16))
         #'<IfII', filecrc, filedate, self.byteposition, len(EntryData))
         self.FirstData[filename] = {
            'crc': filecrc,
            'date': filedate,
            'position': datapos,
            'length': datalen
         }
      
      # Remember the header offset to firstblobs.
      self.FirstHeaderSize = self.totalread

      # Reset reader position stuff now.
      self.totalread = FirstSize + 12 # offset by the file header too
      self.finalreader.seek(self.totalread)

      self.SecondCount = struct.unpack('<I', self.Read(4))[0]

      # Read data.
      for i in range(self.SecondCount):
         filename_len = struct.unpack('<I', self.Read(4))[0]
         filename = self.Read(filename_len).decode('latin-1')
         link_len = struct.unpack('<I', self.Read(4))[0]
         link = self.Read(link_len).decode('latin-1')
         filecrc, filedate, datapos, datalen = struct.unpack('<ILII', self.Read(16))
         #'<IfII', filecrc, filedate, self.byteposition, len(EntryData))
         self.SecondData[filename] = {
            'crc': filecrc,
            'date': filedate,
            'link': link,
            'position': datapos,
            'length': datalen
         }
      
      # Remember the header offset to firstblobs.
      self.SecondHeaderSize = self.totalread
      self.IsLoaded = True
   def ReadFirst(self, filename):
      self.finalreader.seek( ( self.FirstData[filename]['position'] + self.FirstHeaderSize) )
      TheData = self.finalreader.read(self.FirstData[filename]['length'])
      TheData = lzma.decompress(TheData)
      TheCRC = zlib.crc32(TheData)
      print(f"""
Read FirstBlob bytes to memory.
Filename: {filename}
Expected Hash: {self.FirstData[filename]['crc']}
Calculated Hash: {TheCRC}
Decompressed Data Size: {len(TheData)}
""")

      if self.FirstData[filename]["crc"] != TheCRC:
         print('CRC hash failure.')
         raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
      return TheData
   def WriteFirst(self, filename, dest = '.'):
      if isinstance(filename, Path):
         dest.join(filename)
      else:
         dest = f'{dest}/{filename}'
      print(f'FirstDest: {dest}')
      with open(dest, 'wb') as blob:
         self.finalreader.seek( ( self.FirstData[filename]['position'] + self.FirstHeaderSize) )
         TheData = self.finalreader.read(self.FirstData[filename]['length'])
         TheData = lzma.decompress(TheData)
         TheCRC = zlib.crc32(TheData)
         print(f"""
Write FirstBlob bytes to {dest}.
Filename: {filename}
Expected Hash: {self.FirstData[filename]['crc']}
Calculated Hash: {TheCRC}
Decompressed Data Size: {len(TheData)}
""")

         if self.FirstData[filename]["crc"] != TheCRC:
            print('CRC hash failure.')
            raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
         blob.write(TheData)
         blob.flush()
         blob.close()
   def ReadSecond(self, filename):
      self.finalreader.seek( ( self.SecondData[filename]['position'] + self.SecondHeaderSize) )
      TheData = self.finalreader.read(self.SecondData[filename]['length'])
      TheData = lzma.decompress(TheData)
      TheCRC = zlib.crc32(TheData)
      print(f"""
Read Secondblob bytes to memory.
Filename: {filename}
Expected Hash: {self.FirstData[filename]['crc']}
Calculated Hash: {TheCRC}
Decompressed Data Size: {len(TheData)}
""")

      if self.SecondData[filename]["crc"] != TheCRC:
         print('CRC hash failure.')
         raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
      return TheData
   def WriteSecond(self, filename, dest = '.'):
      if isinstance(filename, Path):
         dest.join(filename)
      else:
         dest = f'{dest}/{filename}'
      print(f'Second Dest: {dest}')
      with open(dest, 'wb') as blob:
         self.finalreader.seek( ( self.SecondData[filename]['position'] + self.SecondHeaderSize) )
         TheData = self.finalreader.read(self.SecondData[filename]['length'])
         TheData = lzma.decompress(TheData)
         TheCRC = zlib.crc32(TheData)
         print(f"""
Write FirstBlob bytes to {dest}.
Filename: {filename}
Expected Hash: {self.FirstData[filename]['crc']}
Calculated Hash: {TheCRC}
Decompressed Data Size: {len(TheData)}
""")

         if self.SecondData[filename]["crc"] != TheCRC:
            print('CRC hash failure.')
            raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
         blob.write(TheData)
         blob.flush()
         blob.close()

class FinalFileReaderv1(object):
   def __init__(self) -> None:
      print('Created FileFormat 111 object.')
      self.IsLoaded = False
      self.FirstData = {}
      self.SecondData = {}

      self.FirstHeaderSize = 0
      self.SecondHeaderSize = 0

      self.finalreader = None
      self.totalread = 0
   def Read(self, leng):
      return self.ReadBytes(leng) # Lazy way to do this
   def ReadBytes(self, leng):
      self.totalread = self.totalread + leng
      return self.finalreader.read(leng)
   def Load(self, file):
      self.finalreader = open(file, 'rb')
      HeaderID, FirstSize, SecondSize = struct.unpack('<ILL', self.ReadBytes(12))

      if HeaderID != 111:
         print(f'Unexpected header ID: {HeaderID}')
         raise Exception("This is not a valid file format to read.")
         return

      self.FirstCount = struct.unpack('<I', self.Read(4))[0]

      # Read data.
      for i in range(self.FirstCount):
         filename_len = struct.unpack('<I', self.Read(4))[0]
         filename = self.Read(filename_len).decode('latin-1')
         SteamVer, SteamUIVer = struct.unpack('<II', self.Read(8))
#'<ILIII'
#zlib.crc32(MyData),
#filedate,
#positioninchunk
#chunkposition
#mylength
#chunklength
         filecrc, filedate, datapos, chunkpos, datalen, chunklen = struct.unpack('<ILIIII', self.Read(24))
         self.FirstData[filename] = {
            'crc': filecrc,
            'date': filedate,
            'chunk_position': chunkpos,
            'position': datapos,
            'length': datalen,
            'chunk_length': chunklen,
            'Steam_Version': SteamVer,
            'SteamUI_Version': SteamUIVer
         }
      
      # Remember the header offset to firstblobs.
      self.FirstHeaderSize = self.totalread

      # Reset reader position stuff now.
      self.totalread = FirstSize + 12 # offset by the file header too
      self.finalreader.seek(self.totalread)

      self.SecondCount = struct.unpack('<I', self.Read(4))[0]

      # Read data.
      for i in range(self.SecondCount):
         filename_len = struct.unpack('<I', self.Read(4))[0]
         filename = self.Read(filename_len).decode('latin-1')
         link_len = struct.unpack('<I', self.Read(4))[0]
         link = self.Read(link_len).decode('latin-1')
         filecrc, filedate, datapos, chunkpos, datalen, chunklen = struct.unpack('<ILIIII', self.Read(24))
         self.SecondData[filename] = {
            'crc': filecrc,
            'date': filedate,
            'link': link,
            'chunk_position': chunkpos,
            'position': datapos,
            'length': datalen,
            'chunk_length': chunklen
         }
      
      # Remember the header offset to firstblobs.
      self.SecondHeaderSize = self.totalread
      self.IsLoaded = True
      print(f'Total Blobs {len(self.SecondData) + len(self.FirstData)}')
   def ReadFirst(self, filename):
      self.finalreader.seek( ( self.FirstData[filename]['chunk_position'] + self.FirstHeaderSize) )
      ChunkData = self.finalreader.read(self.FirstData[filename]['chunk_length'])
      ChunkData = pylzma.decompress(ChunkData)
      TheData = ChunkData[self.FirstData[filename]['position']:self.FirstData[filename]['position']+self.FirstData[filename]['length']]
      TheCRC = zlib.crc32(TheData)
      print(f"""
Read FirstBlob bytes to memory.
Filename: {filename}
Expected Hash: {self.FirstData[filename]['crc']}
Calculated Hash: {TheCRC}
Chunk Size: {self.FirstData[filename]['chunk_length']}
Decompressed Data Size: {len(TheData)}
""")

      if self.FirstData[filename]["crc"] != TheCRC:
         print(f'CRC hash failure for {filename}')
         raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
      else:
         print(f'CRC matches. - {filename}')
      return TheData
   def WriteFirst(self, filename, dest = '.'):
      if isinstance(filename, Path):
         dest.join(filename)
      else:
         dest = f'{dest}/{filename}'
      print(f'First Dest: {dest}')
      with open(dest, 'wb') as blob:
         self.finalreader.seek( ( self.FirstData[filename]['chunk_position'] + self.FirstHeaderSize) )
         ChunkData = self.finalreader.read(self.FirstData[filename]['chunk_length'])
         ChunkData = pylzma.decompress(ChunkData)
         TheData = ChunkData[self.FirstData[filename]['position']:self.FirstData[filename]['position']+self.FirstData[filename]['length']]
         TheCRC = zlib.crc32(TheData)
         print(f"""
Write FirstBlob to {dest}
Filename: {filename}
Expected Hash: {self.FirstData[filename]['crc']}
Calculated Hash: {TheCRC}
Chunk Size: {self.FirstData[filename]['chunk_length']}
Decompressed Data Size: {len(TheData)}
""")
         
         if self.FirstData[filename]["crc"] != TheCRC:
            print(f'CRC hash failure for {filename}.')
            raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
         blob.write(TheData)
         blob.flush()
         blob.close()
   def ReadSecond(self, filename):
      self.finalreader.seek( ( self.SecondData[filename]['chunk_position'] + self.SecondHeaderSize) )
      ChunkData = self.finalreader.read(self.SecondData[filename]['chunk_length'])
      ChunkData = pylzma.decompress(ChunkData)
      print(f'size: {len(ChunkData)}')
      TheData = ChunkData[self.SecondData[filename]['position']:self.SecondData[filename]['position']+self.SecondData[filename]['length']]
      TheCRC = zlib.crc32(TheData)
      print(f"""
Read SecondBlob to memory
Filename: {filename}
Expected Hash: {self.SecondData[filename]['crc']}
Calculated Hash: {TheCRC}
Chunk Size: {self.SecondData[filename]['chunk_length']}
Decompressed Data Size: {len(TheData)}
""")

      if self.SecondData[filename]["crc"] != TheCRC:
         print('CRC hash failure.')
         raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
      return TheData
   def WriteSecond(self, filename, dest = '.'):
      if isinstance(filename, Path):
         dest.join(filename)
      else:
         dest = f'{dest}/{filename}'
      print(f'Second Dest: {dest}')
      with open(dest, 'wb') as blob:
         self.finalreader.seek( ( self.SecondData[filename]['chunk_position'] + self.SecondHeaderSize) )
         ChunkData = self.finalreader.read(self.SecondData[filename]['chunk_length'])
         ChunkData = pylzma.decompress(ChunkData)
         TheData = ChunkData[self.SecondData[filename]['position']:self.SecondData[filename]['position']+self.SecondData[filename]['length']]
         TheCRC = zlib.crc32(TheData)
         print(f"""
Write second blob to {dest}
Filename: {filename}
Expected Hash: {self.SecondData[filename]['crc']}
Calculated Hash: {TheCRC}
Decompressed Data Size: {len(TheData)}
""")

         if self.SecondData[filename]["crc"] != TheCRC:
            print(f'CRC Hash failure for {filename}')
            raise Exception('The blob data is corrupted.') # Detect potenial drive failure / corrupted file.
         
         blob.write(TheData)
         blob.flush()
         blob.close()

# For reading non final files
class BillyReader(object):
   def __init__(self) -> None:
      self.IsLoaded = False
      self.blobs = -1
      self.data = {}
      self.headersize = 0
      self.totalread = 0
   def Read(self, leng):
      self.totalread = self.totalread + leng
      return self.f.read(leng)
   def Load(self, filename):
      self.f = open(filename, 'rb')
      self.blobs = struct.unpack('<I', self.Read(4))[0]

      # Read data.
      for i in range(self.blobs):
         filename_len = struct.unpack('<I', self.Read(4))[0]
         filename = self.Read(filename_len).decode('latin-1')
         filecrc, filedate, datapos, datalen = struct.unpack('<ILII', self.Read(16))
         #'<IfII', filecrc, filedate, self.byteposition, len(EntryData))
         self.data[filename] = {
            'crc': filecrc,
            'date': filedate,
            'position': datapos,
            'length': datalen
         }
      self.headersize = self.totalread
      self.IsLoaded = True
   def SaveBlob(self, blobname):
      with open(f'./test/{blobname}', 'wb') as blob:
         self.f.seek( ( self.data[blobname]['position'] + self.headersize) )
         TheData = self.f.read(self.data[blobname]['length'])
         TheData = lzma.decompress(TheData)
         print(f'Written: {zlib.crc32(TheData)}')
         print(f'Packed: {self.data[blobname]["crc"]}')
         blob.write(TheData)
         blob.flush()
         blob.close()
      

#br = BillyReader()
#br.Load('./second.blobs')
#br.SaveBlob('secondblob.bin.2004-08-10 12_00_45 - Counter-Strike Source Beta (Pre-loading to cyber cafés) (C)')
#print()
class Serialiser(object):
   def __init__(self, name, SecondBlobMode = False, RandomGroup = False):
      self.f = open(f'./{name}.blobs.todo', 'wb')
      self.name = name
      self.byteposition = 0
      self.entrylist = []
      self.pendingentry = []
      self.SecondBlobMode = SecondBlobMode
      self.GroupSize = 10
      self.ticker = 0
      # DIRTY HACK
      
      self.FilesFolder = './files/'
      self.BlobsFolder = f'{self.FilesFolder}blobs/'
      self.CacheFolder = f'{self.FilesFolder}cache/'

      self.SecondBlobs = []
      self.FirstBlobs = []

      BlobsFiles = sorted(Path('./files/blobs/').iterdir(), key=path.getmtime)

      for item in BlobsFiles:
         filename = item.name.replace('files/blobs/', '')

         if item.is_file() == False:
            continue # Fucking folder
         elif filename.startswith("secondblob.bin"):
            self.SecondBlobs.append(filename)
         elif filename.startswith("firstblob.bin"):
            self.FirstBlobs.append(filename)
   def CreateChunks(self):
      # Create chunks
      self.SecondChunks = [self.SecondBlobs[i:i + self.GroupSize] for i in range(0, len(self.SecondBlobs), self.GroupSize)]
      self.FirstChunks = [self.FirstBlobs[i:i + self.GroupSize] for i in range(0, len(self.FirstBlobs), self.GroupSize)]
   def GetFirstBlob(self, SecondTarget):
      SecondBlobDate = path.getmtime(f"{self.BlobsFolder}{SecondTarget}")
   
      FirstTarget = -1
      LastFirstIndex = len(self.FirstBlobs)
      LastFirstBlobDate = 0

      # New solving logic
      IsSolved = False

      while not IsSolved:
         if LastFirstIndex < 0:
            # Do not loop forever.
            break
         else:
            LastFirstIndex = LastFirstIndex - 1
            LastFirstBlobDate = path.getmtime(f"{self.BlobsFolder}{self.FirstBlobs[LastFirstIndex]}")

         # Try to find same date / older.
         if LastFirstBlobDate <= SecondBlobDate:
            try:
               FirstTarget = self.FirstBlobs[LastFirstIndex]
               IsSolved = True
            except:
               continue
      
      if IsSolved == False and len(self.FirstBlobs) > 0:
         return False
      elif IsSolved == False:
         return False
      else:
         return FirstTarget
   def WriteBytes(self, bytes):
      self.byteposition = self.byteposition + len(bytes)
      self.f.write(bytes)
   def Flush(self):
      self.f.flush()
   def Process(self):
      if self.SecondBlobMode:
         for chunk in self.SecondChunks:
            PendingEntry = []
            TheData = b''
            for name in chunk:
               print(name)
               chunkoffset = len(TheData)
               MyData = None
               with open(f'./files/blobs/{name}', 'rb') as f:
                  MyData = f.read()
                  TheData = TheData + MyData
               encodedname = name.encode('latin-1')
               EntryHeader = (struct.pack('<I', len(encodedname)) + encodedname)
               # Preprocess firstblob
               FirstBlob = self.GetFirstBlob(name)
               EntryHeader = EntryHeader + ( struct.pack('<I', len(FirstBlob.encode('latin-1'))) + FirstBlob.encode('latin-1') )
               EntryHeader = EntryHeader + struct.pack('<ILIII', zlib.crc32(MyData), int(round(path.getmtime(f"./files/blobs/{name}"))), chunkoffset, self.byteposition, len(MyData))
               PendingEntry.append(EntryHeader)
               #self.entrylist.append(EntryHeader)
            TheData = lzma.compress(TheData)
            for Pending in PendingEntry:
               Final = Pending + struct.pack('<I', len(TheData))
               self.entrylist.append(Final)
            self.WriteBytes(TheData)
            self.Flush()
      else:
         for chunk in self.FirstChunks:
            PendingEntry = []
            TheData = b''
            for name in chunk:
               print(name)
               chunkoffset = len(TheData)
               MyData = None
               with open(f'./files/blobs/{name}', 'rb') as f:
                  MyData = f.read()
                  TheData = TheData + MyData
               encodedname = name.encode('latin-1')
               EntryHeader = (struct.pack('<I', len(encodedname)) + encodedname)
               Info = ReadInfo(MyData)
               EntryHeader = EntryHeader + struct.pack('<II', Info[0], Info[1])
               #if self.SecondBlobMode:
                  # Preprocess firstblob
               #   FirstBlob = self.GetFirstBlob(name)
               #   EntryHeader = EntryHeader + ( struct.pack('<I', len(FirstBlob)) + FirstBlob.encode('latin-1') )
               EntryHeader = EntryHeader + struct.pack('<ILIII',
                                                       zlib.crc32(MyData),
                                                       int(round(path.getmtime(f"./files/blobs/{name}"))), 
                                                       chunkoffset,
                                                       self.byteposition,
                                                       len(MyData))
               PendingEntry.append(EntryHeader)
            TheData = lzma.compress(TheData)
            for Pending in PendingEntry:
               Final = Pending + struct.pack('<I', len(TheData))
               self.entrylist.append(Final)
            self.WriteBytes(TheData)
            self.Flush()
   def Finalise(self):
      self.f.flush()
      self.f.close()

      OldFile = open(f'./{self.name}.blobs.todo', 'rb')
      with open(f'./{self.name}.blobs', 'wb') as f:
         f.write(struct.pack('<I', len(self.entrylist)))
         f.flush()
         for entry in self.entrylist:
            f.write(entry)
            f.flush()
         f.write(OldFile.read())
         f.flush()
         f.close()
      OldFile.close()

      # Try to clean up left over.
      try:
         os.remove(f'./{self.name}.blobs.todo')
      except:
         pass
         

# This code below creates first and second blob packed files.

#FirstSerialise = Serialiser('second')

#for i in range(len(SecondBlobs)):
#   File = open(f'{BlobsFolder}{SecondBlobs[i]}', 'rb')
#   FileData = File.read()
#   File.close()
#   FileDate = path.getmtime(f"{BlobsFolder}{SecondBlobs[i]}")
#   FirstSerialise.AddEntry(SecondBlobs[i], zlib.crc32(FileData), FileDate)
#   print(SecondBlobs[i])
#FirstSerialise.Finalise()

#SecSerialise = Serialiser('second', True)
#SecSerialise.Process()
#SecSerialise.Finalise()

#print()
#FirstSerialise = Serialiser('first')
#FirstSerialise.Process()
#FirstSerialise.Finalise()

#print()
#newfinal = FinalFileReaderv1()
#newfinal.Load('./The.blobs')
#newfinal.ReadSecond('secondblob.bin.2006-04-15 00_26_14')
#print()
#First = open('./first.blobs', 'rb')
#Second = open('./second.blobs', 'rb')
#FirstSize = os.path.getsize('./first.blobs')
#SecondSize = os.path.getsize('./second.blobs')
   
#with open('./The.blobs', 'wb') as f:
#   FileHeader = struct.pack('<ILL', 111, FirstSize, SecondSize)
#   f.write(FileHeader)
#   f.write(First.read())
#   f.flush()
#   f.write(Second.read())
#   f.flush()
#   f.close()

#for i in range(len(FirstBlobs)):
#   File = open(f'{BlobsFolder}{FirstBlobs[i]}', 'rb')
#   FileData = File.read()
#   File.close()
#   FileDate = path.getmtime(f"{BlobsFolder}{FirstBlobs[i]}")
#   FirstSerialise.AddEntry(FirstBlobs[i], zlib.crc32(FileData), FileDate)
#   print(FirstBlobs[i])
#FirstSerialise.Finalise()


# This code merges files. Needs to be a function.

#First = open('./first.blobs', 'rb')
#Second = open('./second.blobs', 'rb')
#FirstSize = os.path.getsize('./first.blobs')
#SecondSize = os.path.getsize('./second.blobs')

#with open('./final.blobs', 'wb') as f:
#   FileHeader = struct.pack('<ILL', 110, FirstSize, SecondSize)
#   f.write(FileHeader)
#   f.write(First.read())
#   f.flush()
#   f.write(Second.read())
#   f.flush()
#   f.close()