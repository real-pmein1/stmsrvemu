import datetime
import os
from random import randint
import struct
from threading import Thread
from time import sleep
import time
import zlib
import PySimpleGUI as psg
from pathlib import Path
from os import path

from GenerateDB import BillyReader, Serialiser
from py7zlib import pylzma
from blobreader import ReadBytes as ReadInfo
import simpleaudio as sa

# Custom vars
CustomTheme = {"BACKGROUND": "#4c5844", "TEXT": "#ffffff", "INPUT": "#ffffff", "TEXT_INPUT": "#000000", "SCROLL": "#5a6a50",
                   "BUTTON": ("#889180", "#4c5844"), "PROGRESS": ("#958831", "#3e4637"), "BORDER": 1, "SLIDER_DEPTH": 0, "PROGRESS_DEPTH": 0,
                   "COLOR_LIST": ["#ff00fd", "#ff00fd", "#ff00fd", "#ff00fd"], "DESCRIPTION": ["Grey", "Green", "Vintage"], }


# TODO: Match bytes between blobs and sort them into chunks to help out the compression algorithm??

global EtaVal
EtaVal = ''
# Nuitka shit
windowico = path.join(path.dirname(__file__), "icon.ico")

FilesFolder = './files/'
BlobsFolder = f'{FilesFolder}blobs/'
CacheFolder = f'{FilesFolder}cache/'

SecondBlobs = []
FirstBlobs = []

BlobsFiles = sorted(Path('./files/blobs/').iterdir(), key=path.getmtime)

def PopulateRows():
   for item in BlobsFiles:
      filename = item.name.replace('files/blobs/', '')

      if item.is_file() == False:
         continue # Fucking folder
      elif filename.startswith("secondblob.bin"):
         SecondBlobs.append(filename)
      elif filename.startswith("firstblob.bin"):
         FirstBlobs.append(filename)

PopulateRows()

ProgressBarTotal = len(BlobsFiles) + 100
TotalProcessed = 1

psg.LOOK_AND_FEEL_TABLE['SteamGreen'] = CustomTheme
psg.theme("SteamGreen")
psg.set_options(font=('Verdana', 9)) #icon=windowico)

loadinglayout = [
    [psg.Push(), psg.Text("Blob Packager - 1.1", justification='center'), psg.Push()],
    [psg.Multiline(
       'Debug Area\r\n', 
       autoscroll=True, 
       auto_refresh=True, 
       disabled=True, 
       expand_x=True, 
       expand_y=True,
       background_color='#3e4637',
       text_color='#ffffff',
       key='-UPDATE-')],
    [psg.ProgressBar(max_value=ProgressBarTotal, orientation='h', size=(50,20), key='-PB-')],
    [psg.Push(), psg.Button('Package', key='-START-', button_color=('#c4b550', '#4c5844')), psg.Combo(['Slowest', 'Slower', 'Slow', 'Mixed', 'Fast', 'Faster', 'Fastest'], default_value='Mixed', key='-SPEED-'), psg.Push()],
    [psg.Text('', key='-STAGE-'), psg.Text('', key='-ETATEX-')]
]

window = psg.Window("Blob Packager", loadinglayout, size=(500, 300), finalize=True, disable_close=False)

def Pack(size, window):
    global FirstBlobs, TotalProcessed
    window.write_event_value(('-STATUS-'), 'Stage 1 of 3')

    First = Serialiser('second', True)
    if size == -1:
       First.GroupSize = randint(4, 6)
    else:
       First.GroupSize = size
    First.CreateChunks()
    for chunk in First.SecondChunks:
        PendingEntry = []
        TheData = b''
        for name in chunk:
            window.write_event_value(('-MSG-'), f'Chunks {len(First.SecondChunks)} | {name}')
            chunkoffset = len(TheData)
            MyData = None
            with open(f'./files/blobs/{name}', 'rb') as f:
                MyData = f.read()
                TheData = TheData + MyData
            encodedname = name.encode('latin-1')
            EntryHeader = (struct.pack('<I', len(encodedname)) + encodedname)
            # Preprocess firstblob
            FirstBlob = First.GetFirstBlob(name)
            EntryHeader = EntryHeader + ( struct.pack('<I', len(FirstBlob.encode('latin-1'))) + FirstBlob.encode('latin-1') )
            MyHash = zlib.crc32(MyData)
            EntryHeader = EntryHeader + struct.pack('<ILIII', MyHash, int(round(path.getmtime(f"./files/blobs/{name}"))), chunkoffset, First.byteposition, len(MyData))
            PendingEntry.append(EntryHeader)
            TotalProcessed = TotalProcessed + 1
            window.write_event_value(('-UPPB-'), TotalProcessed)
            #self.entrylist.append(EntryHeader)
        TheData = pylzma.compress(TheData, eos=0, dictionary=27, fastBytes=255, literalContextBits=8, literalPosBits=2)
        #TheData = pylzma.compress(TheData, eos=1, dictionary=27, fastBytes=255, literalContextBits=4)
        for Pending in PendingEntry:
           Final = Pending + struct.pack('<I', len(TheData))
           First.entrylist.append(Final)
        First.WriteBytes(TheData)
        First.Flush()
    window.write_event_value(('-STATUS-'), 'Stage 2 of 3')
    First.Finalise()

    Second = Serialiser('first', False)
    if size == -1:
       Second.GroupSize = randint(4, 6)
    else:
       Second.GroupSize = size
    Second.CreateChunks()
    for chunk in Second.FirstChunks:
        PendingEntry = []
        TheData = b''
        for name in chunk:
           window.write_event_value(('-MSG-'), f'Chunks {len(Second.FirstChunks)}.{Second.GroupSize} | {name}')
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
           MyHash = zlib.crc32(MyData)
           EntryHeader = EntryHeader + struct.pack('<ILIII',
                                                       zlib.crc32(MyData),
                                                       int(round(path.getmtime(f"./files/blobs/{name}"))), 
                                                       chunkoffset,
                                                       Second.byteposition,
                                                       len(MyData))
           PendingEntry.append(EntryHeader)
           TotalProcessed = TotalProcessed + 1
           window.write_event_value(('-UPPB-'), TotalProcessed)

        TheData = pylzma.compress(TheData, eos=0, dictionary=27, fastBytes=255, literalContextBits=8, literalPosBits=2)  
        #TheData = pylzma.compress(TheData, eos=1, dictionary=27, fastBytes=255, literalContextBits=4)
        for Pending in PendingEntry:
            Final = Pending + struct.pack('<I', len(TheData))
            Second.entrylist.append(Final)
        Second.WriteBytes(TheData)
        Second.Flush()
    window.write_event_value(('-STATUS-'), 'Stage 3 of 3')
    Second.Finalise()
    First = open('./first.blobs', 'rb')
    Second = open('./second.blobs', 'rb')
    FirstSize = os.path.getsize('./first.blobs')
    SecondSize = os.path.getsize('./second.blobs')
    
    with open('./The.blobs', 'wb') as f:
      FileHeader = struct.pack('<ILL', 111, FirstSize, SecondSize)
      f.write(FileHeader)
      f.write(First.read())
      f.flush()
      f.write(Second.read())
      f.flush()
      f.close()
    window.write_event_value(('-UPPB-'), ProgressBarTotal)
    try:
      os.remove('./first.blobs')
      os.remove('./second.blobs')
    except:
      pass
    else:
      window.write_event_value(('-MSG-'), 'Cleaned up temp files.')
    window.write_event_value(('-MSG-'), 'Saved final file to ./The.blobs\r\nYou can now close this window.')
    window.DisableClose = False

    wave_obj = sa.WaveObject.from_wave_file(path.join(path.dirname(__file__), "finish3a.wav"))
    play_obj = wave_obj.play()

def GetSize(val):
   if val == 'Slowest':
      window['-UPDATE-'].Update(f'Using chunksize Slowest (10)\n', append = True) 
      return 10 # 952.3
   elif val == 'Slower':
      window['-UPDATE-'].Update(f'Using chunksize Slower (7)\n', append = True) 
      return 7 # 1 GB
   elif val == 'Slow':
      window['-UPDATE-'].Update(f'Using chunksize Slow (5)\n', append = True) 
      return 5 # 1.1 GB
   elif val == 'Auto':
      window['-UPDATE-'].Update(f'Using chunksize Auto (4 - 6)\n', append = True) 
      return -1 # 1.0 - 1.1 GB probably
   elif val == 'Fast':
      window['-UPDATE-'].Update(f'Using chunksize Fast (4)\n', append = True) 
      return 4 # 1.1 GB - Probably a good default
   elif val == 'Faster':
      window['-UPDATE-'].Update(f'Using chunksize Faster (3)\n', append = True) 
      return 3 # 1.2 GB
   elif val == 'Fastest':
      window['-UPDATE-'].Update(f'Using chunksize Fastest (2)\n', append = True) 
      return 2 # 1.37 GB
   else:
      # Try to make into a int
      test = -1
      try:
         test = int(val)
      except:
         window['-UPDATE-'].Update(f'Invalid chunk size defaulting to Mixed.\n', append = True) 
         return -1
      else:
         window['-UPDATE-'].Update(f'Using custom chunksize: {test}\r\n', append = True) 
         return test

def WindowRefresher(window):
   while True:
      sleep(0.5)
      window.refresh()

thread = Thread(target=WindowRefresher, args=(window,))
thread.daemon = True
thread.start()

start = None
while True:
   event, values = window.read()

   print(event)
   if event in (psg.WIN_CLOSED, 'Exit'):
      break # future clean up code here.
   elif '-START-' in event:
      if len(BlobsFiles) == 1:
         psg.popup('Your blobs folder contains a single file.\r\nDid you forget to change from using preprocessed?')
         continue
      
      window['-START-'].Update(disabled = True)
      window.DisableClose = True
      #thread2 = Thread(target=EtaThreader, args=(time.time(),window,))
      #thread2.daemon = True
      #thread2.start()
      start = time.time()
      thread3 = Thread(target=Pack, args=(GetSize(values['-SPEED-']),window))
      thread3.daemon = True
      thread3.start()
   if '-ETA-' in event:
      window['-ETATEX-'].Update(value=values['-ETA-'])
   if '-STATUS-' in event:
      window['-STAGE-'].Update(value=values['-STATUS-'])
   if '-MSG-' in event:
      window['-UPDATE-'].Update(f'{values["-MSG-"]}\r\n', append = True)
   if '-UPPB-' in event:
      #TotalProcessed = values['-UPPB-']
      window['-PB-'].update(current_count=values['-UPPB-'])
      remaining = ((time.time() - start) / values['-UPPB-']) * (ProgressBarTotal - values['-UPPB-'])
        
      mins, sec = divmod(remaining, 60)
      time_str = f"Time Remaining: {int(mins):02} Minutes and {sec:05.2f} Seconds."
      window['-ETATEX-'].update(value=time_str)
