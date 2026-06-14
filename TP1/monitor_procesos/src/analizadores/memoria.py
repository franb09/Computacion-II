import time
import os
import procfs

def recolectar_memoria(snapshot):
    while True:
        try:
            datos_memoria = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                stat = procfs.leer_stat(pid)
                status = procfs.leer_status(pid)
                
                if stat and status:
                    minflt = stat[9] if len(stat) > 9 else "0"
                    majflt = stat[11] if len(stat) > 11 else "0"
                    
                    datos_memoria[pid] = {
                        "comando": str(status.get("Name", "Desconocido")),
                        "vmsize": status.get("VmSize", "0 kB").replace(" kB", "").strip(),
                        "vmrss":  status.get("VmRSS", "0 kB").replace(" kB", "").strip(),
                        "vmdata": status.get("VmData", "0 kB").replace(" kB", "").strip(),
                        "vmstk":  status.get("VmStk", "0 kB").replace(" kB", "").strip(),
                        "vmswap": status.get("VmSwap", "0 kB").replace(" kB", "").strip(),
                        "minflt": minflt,
                        "majflt": majflt
                    }
            
            snapshot["memoria"] = datos_memoria
            time.sleep(3) 
            
        except Exception as e:
            snapshot["memoria"] = {"ERROR": {"comando": f"CRASH: {e}"}}
            time.sleep(3)