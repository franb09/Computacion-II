import os

def leer_stat(pid):
    path = f"/proc/{pid}/stat"
    if not os.path.exists(path):
        return None
        
    try:
        with open(path, 'r') as f:
            data = f.read().strip()
            return data.split()
    except (FileNotFoundError, PermissionError):
        return None

def leer_status(pid):
    path = f"/proc/{pid}/status"
    if not os.path.exists(path):
        return None
        
    status_dict = {}
    try:
        with open(path, 'r') as f:
            for linea in f:
                if ':' in linea:
                    key, value = linea.split(':', 1)
                    status_dict[key.strip()] = value.strip()
        return status_dict
    except (FileNotFoundError, PermissionError):
        return None

def leer_jiffies_sistema():
    try:
        with open('/proc/stat', 'r') as f:
            linea_cpu = f.readline().split()
            # Sumamos todos los valores desde el índice 1 en adelante
            return sum(int(x) for x in linea_cpu[1:])
    except (FileNotFoundError, PermissionError):
        return 0

def leer_jiffies_proceso(pid):
    stat = leer_stat(pid)
    if stat and len(stat) > 14:
        try:
            utime = int(stat[13])
            stime = int(stat[14])
            return utime + stime
        except ValueError:
            return 0
    return 0
