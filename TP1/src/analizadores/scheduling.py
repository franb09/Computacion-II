import time
import os
import procfs

#Agregue policy y rt_priority. Ademas de cambiar que ahora la lista cuente desde 0 hasta el 40.
#Agregue Context switches (voluntary y nonvoluntary) de status y la Afinidad de CPU (cpus_allowed_list).

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
                        "threads": stat[19],
                        "core": stat[38],
                        "rt_priority": stat[39], 
                        "policy": stat[40],     
                        "cpus_allowed": status.get("Cpus_allowed_list", "N/A"),
                        "ctx_vol": status.get("voluntary_ctxt_switches", "0"),
                        "ctx_invol": status.get("nonvoluntary_ctxt_switches", "0")
                    }
            
            snapshot["scheduling"] = datos_sched
            time.sleep(intervalo.value)
            
        except Exception as e:
            snapshot["scheduling"] = {"ERROR": {"comando": f"CRASH: {e}", "prioridad": "0", "nice": "0", "threads": "0", "core": "0"}}
            time.sleep(intervalo.value)