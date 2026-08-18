import time
import os
import procfs

#Se agrupo los segmentos en maps, y sume VmHWM 

def recolectar_memoria(snapshot,intervalo):
    while True:
        try:
            datos_memoria = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                status = procfs.leer_status(pid)
                maps = procfs.leer_maps(pid) 
            
                if status:
                    datos_memoria[pid] = {
                        "comando": status.get("Name", "Desconocido"),
                        "vmsize": status.get("VmSize", "0 kB"),
                        "vmrss": status.get("VmRSS", "0 kB"),
                        "vmhwm": status.get("VmHWM", "0 kB"), 
                        "text": f"{maps.get('text', 0):.1f} kB",
                        "data": f"{maps.get('data', 0):.1f} kB",
                        "heap": f"{maps.get('heap', 0):.1f} kB",
                        "stack": f"{maps.get('stack', 0):.1f} kB",
                        "shared": f"{maps.get('shared', 0):.1f} kB"
                    }
            snapshot["memoria"] = datos_memoria
            time.sleep(intervalo.value)
            
        except Exception as e:
            snapshot["memoria"] = {"ERROR": {"comando": f"CRASH: {e}"}}
            time.sleep(intervalo.value)