import time
import os
import procfs

def recolectar_threads(snapshot):
    """
    Analizador independiente para la vista de Threads.
    Actualiza snapshot['threads'] cada 3 segundos.
    """
    while True:
        try:
            datos_threads = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                status = procfs.leer_status(pid)
                if not status:
                    continue
                
                task_path = f"/proc/{pid}/task"
                if not os.path.exists(task_path) or not os.access(task_path, os.R_OK):
                    continue

                try:
                    tids = os.listdir(task_path)
                    total_threads = len(tids)
                    
                    ejemplos_hilos = []
                    for tid in tids[:4]:
                        t_status = procfs.leer_status(f"{pid}/task/{tid}")
                        if t_status:
                            t_name = t_status.get("Name", "Desc")
                            t_state = t_status.get("State", "?").split()[0] 
                            ejemplos_hilos.append(f"{tid}:[{t_state}] {t_name[:10]}")
                            
                    if total_threads > 0:
                        datos_threads[pid] = {
                            "comando": str(status.get("Name", "Desconocido")),
                            "total_threads": total_threads,
                            "ejemplos": ", ".join(ejemplos_hilos)
                        }
                except PermissionError:
                    pass
            
            snapshot["threads"] = datos_threads
            time.sleep(3) 
            
        except Exception as e:
            snapshot["threads"] = {"ERROR": {"comando": f"CRASH: {e}", "total_threads": 0, "ejemplos": ""}}
            time.sleep(3)