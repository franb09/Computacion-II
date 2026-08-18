import os
import pwd

#Mantuve las funciones originales que funcionaban y le sume lo que me pidio: 
#Traducción de Uid, una funcion nueva para leer el comando completo(leer_cmdline) y otra funcion para leer /proc/<pid>/maps.

def leer_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "r") as f:
            cmd = f.read()
            return cmd.replace('\x00', ' ').strip()
    except Exception:
        return ""

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
        
        # Traducción de Uid 
        if "Uid" in status_dict:
            uid_real = int(status_dict["Uid"].split()[0])
            try:
                status_dict["User"] = pwd.getpwuid(uid_real).pw_name
            except KeyError:
                status_dict["User"] = str(uid_real)
                
        return status_dict
    except (FileNotFoundError, PermissionError):
        return None

def leer_maps(pid):
    path = f"/proc/{pid}/maps"
    maps_res = {"text": 0, "data": 0, "heap": 0, "stack": 0, "shared": 0}
    try:
        with open(path, 'r') as f:
            for linea in f:
                partes = linea.split()
                if len(partes) < 5: continue
                
                perms = partes[1]
                addrs = partes[0].split('-')
                size_kb = (int(addrs[1], 16) - int(addrs[0], 16)) / 1024 # Tamaño en KB
                
                if len(partes) >= 6:
                    path_name = partes[5]
                    if path_name == '[heap]': maps_res["heap"] += size_kb
                    elif path_name == '[stack]': maps_res["stack"] += size_kb
                    elif 's' in perms: maps_res["shared"] += size_kb
                    elif 'x' in perms: maps_res["text"] += size_kb
                    else: maps_res["data"] += size_kb
                else:
                    if 's' in perms: maps_res["shared"] += size_kb
                    elif 'x' in perms: maps_res["text"] += size_kb
                    else: maps_res["data"] += size_kb
    except (FileNotFoundError, PermissionError):
        pass
    return maps_res

def leer_jiffies_sistema():
    try:
        with open('/proc/stat', 'r') as f:
            linea_cpu = f.readline().split()
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