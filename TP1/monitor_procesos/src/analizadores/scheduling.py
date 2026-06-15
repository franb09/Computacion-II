import time
import os
import procfs

def recolectar_scheduling(snapshot,intervalo):

    while True:
        try:
            datos_sched = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                stat = procfs.leer_stat(pid)
                status = procfs.leer_status(pid)
                if stat and status and len(stat) >= 40:
                    priority = stat[17] 
                    nice = stat[18]     
                    threads = stat[19]  
                    core = stat[38]     
                    
                    datos_sched[pid] = {
                        "comando": str(status.get("Name", "Desconocido")),
                        "prioridad": priority,
                        "nice": nice,
                        "threads": threads,
                        "core": core
                    }
            
            snapshot["scheduling"] = datos_sched
            time.sleep(intervalo.value)
            
        except Exception as e:
            snapshot["scheduling"] = {"ERROR": {"comando": f"CRASH: {e}", "prioridad": "0", "nice": "0", "threads": "0", "core": "0"}}
            time.sleep(intervalo.value)