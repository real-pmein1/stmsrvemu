import httpd, os, subprocess, psutil, logging

import globalvars

class steamweb():
    def __init__(self, http_port, http_ip, apache_root, web_root) :
        log = logging.getLogger("websrv")
        serverid = ""
        log.debug(serverid + "Starting Apache2 web server")
        for file in os.walk("logs"):
            for pidfile in file[2]:
                try:
                    if pidfile.endswith(".pid"):
                        old_proc = pidfile[:-4]
                        log.debug(serverid + "Apache2 process ID found: " + old_proc)
                        process = psutil.Process(int(old_proc))
                        for proc in process.children(recursive=True):
                            proc.kill()
                        process.kill()
                        log.debug(serverid + "Apache2 process  " + old_proc + " killed")
                except Exception as e:
                    log.debug(serverid + "Apache2 error: " + str(e))
                    with open("logs/apache_startup.log", "w") as logfile:
                        logfile.write(str(e))
                finally:
                    if pidfile.endswith(".pid"): os.remove("logs/" + pidfile)

        #if globalvars.steamui_ver < 36 :
        #    http_port = "80"
        #elif len(http_port) > 0: 
        #    http_port = http_port[1:]
        #else:
        #    http_port = "80"
        log.debug(serverid + "Apache2 binary: " + apache_root + "/bin/httpd.exe")
        apache_bin = apache_root + "/bin/httpd.exe"
        apache_bin_dir = apache_bin[:apache_bin.rindex("/")]
        log.debug(serverid + "Apache2 binary folder: " + apache_bin_dir)
        apache_conf_dir = apache_root + "/conf/"
        log.debug(serverid + "Apache2 config folder: " + apache_conf_dir)
        conf_file = apache_conf_dir + http_port + ".conf"
        conf_file_short = "conf/" + http_port + ".conf"
        log.debug(serverid + "Apache2 config file: " + conf_file)
        default_conf_file = apache_conf_dir + "httpd.conf"
        log.debug(serverid + "Apache2 default config file: " + default_conf_file)
        log.debug(serverid + "Apache2 web root folder: " + web_root)

        httpd.check_config(conf_file, http_ip, http_port, web_root, default_conf_file)
        log.debug(serverid + "Apache2 config file created")

        proc = subprocess.Popen(apache_bin + " -f " + conf_file_short, cwd=apache_bin_dir)
        log.debug(serverid + "Apache2 started with process ID " + str(proc.pid))

        with open("logs/" + str(proc.pid) + ".pid", "w") as pid_file:
            pid_file.write(str(proc.pid))
            
            
class check_child_pid():
    def __init__(self):
        self.check_pid()

    def __call__(self):
        self.check_pid()
        
    def check_pid(self):
        log = logging.getLogger("websrv")
        serverid = ""
        try:
            for file in os.walk("logs"):
                for pidfile in file[2]:
                    if pidfile.endswith(".pid"):
                        old_proc = pidfile[:-4]
                        log.debug(serverid + "Apache2 process ID found: " + old_proc)
                        break
            current_process = psutil.Process(int(old_proc))
            children = current_process.children(recursive=True)
            for child in children:
                log.debug(serverid + "Apache2 child process ID found: " + str(child.pid))
                with open("logs/" + str(child.pid) + ".pid", "w") as child_pid_file:
                    child_pid_file.write(str(child.pid))
        except Exception as e:
            log.debug(serverid + "Apache2 error: " + str(e))
            old_proc = "0"