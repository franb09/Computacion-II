import time
import os
import procfs

def recolectar_fds(snapshot, intervalo):
    while True:
        try:
            datos_fds = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                status = procfs.leer_status(pid)
                if not status:
                    continue
                
                fd_path = f"/proc/{pid}/fd"
                if not os.path.exists(fd_path) or not os.access(fd_path, os.R_OK):
                    continue

                try:
                    fds = os.listdir(fd_path)
                    total_fds = len(fds)
                    
                    ejemplos_fds = []
                    for fd in fds[:15]:
                        try:
                            destino = os.readlink(f"{fd_path}/{fd}")
                            tipo = "file"
                            if destino.startswith("socket:"): tipo = "socket"
                            elif destino.startswith("pipe:"): tipo = "pipe"
                            elif destino.startswith("/dev/"): tipo = "tty"
                            
                            ejemplos_fds.append(f"{fd}:[{tipo}] {destino[:15]}")
                        except OSError:
                            pass
                            
                    if total_fds > 0:
                        datos_fds[pid] = {
                            "comando": str(status.get("Name", "Desconocido")),
                            "total_fds": total_fds,
                            "ejemplos": ", ".join(ejemplos_fds)
                        }
                except PermissionError:
                    pass
            
            snapshot["fds"] = datos_fds
            time.sleep(intervalo.value)
            
        except Exception as e:
            snapshot["fds"] = {"ERROR": {"comando": f"CRASH: {e}", "total_fds": 0, "ejemplos": ""}}
            time.sleep(intervalo.value)