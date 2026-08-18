import time
import os
import procfs

#Agregue policy y rt_priority. Ademas de cambiar que ahora la lista cuente desde 0 hasta el 40.

def recolectar_scheduling(snapshot,intervalo):

    while True:
        try:
            datos_sched = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                stat = procfs.leer_stat(pid)
                status = procfs.leer_status(pid)
                
                if stat and len(stat) >= 42 and status:
                    datos_sched[pid] = {
                        "comando": status.get("Name", "Desconocido"),
                        "prioridad": stat[17],
                        "nice": stat[18],
                        "rt_priority": stat[39], 
                        "policy": stat[40],     
                        "cpus_allowed": status.get("Cpus_allowed_list", "N/A")
                    }
            
            snapshot["scheduling"] = datos_sched
            time.sleep(intervalo.value)
            
        except Exception as e:
            snapshot["scheduling"] = {"ERROR": {"comando": f"CRASH: {e}", "prioridad": "0", "nice": "0", "threads": "0", "core": "0"}}
            time.sleep(intervalo.value)