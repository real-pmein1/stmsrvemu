import logging, ConfigParser, sys
from steamemu.config import read_config
from logging.handlers import RotatingFileHandler

config = read_config()
loglevel = config["log_level"]
logtofile = config["log_to_file"]

#LOG LEVELS:
#CRITICAL
#ERROR
#WARNING
#INFO
#DEBUG
#NOTSET
fh = logging.handlers.RotatingFileHandler('logs\\emulator_debug.log', maxBytes=20000000, backupCount=10)
fh.setLevel(logging.DEBUG)
fh2 = logging.handlers.RotatingFileHandler('logs\\emulator_info.log', maxBytes=20000000, backupCount=5)
fh2.setLevel(logging.INFO)
er = logging.handlers.RotatingFileHandler('logs\\emulator_error.log', maxBytes=20000000, backupCount=2)
er.setLevel(logging.WARNING)
ch = logging.StreamHandler(sys.stdout)
if loglevel == "logging.DEBUG" :
    ch.setLevel(logging.DEBUG)
elif loglevel == "logging.INFO" :
    ch.setLevel(logging.INFO)
elif loglevel == "logging.CRITICAL" :
    ch.setLevel(logging.CRITICAL)
elif loglevel == "logging.ERROR" :
    ch.setLevel(logging.ERROR)
elif loglevel == "logging.WARNING" :
    ch.setLevel(logging.WARNING)
elif loglevel == "logging.NOTSET" :
    ch.setLevel(logging.NOTSET)
else :
    ch.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
fh2.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
er.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
ch.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))

root = logging.getLogger()
root.setLevel(logging.DEBUG)
# alternatively:
# root.setLevel(min([fh.level, fh2.level, ch.level, er.level])

root.addHandler(fh)
root.addHandler(fh2)
root.addHandler(ch)
root.addHandler(er)
