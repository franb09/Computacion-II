import time
import os
import procfs

#Hice cambios para que al usar cmdline, se cumpla la exigencia de mostrar el comando completo con sus argumentos.
#Ademas sume "usuario" y "ppid", que eran datos que me faltaban.

def recolectar_resumen(snapshot, intervalo):
    try:
        jiffies_sys_ant = procfs.leer_jiffies_sistema()
        jiffies_proc_ant = {}

        while True:
            datos_resumen = {}
            jiffies_sys_act = procfs.leer_jiffies_sistema()
            delta_sys = jiffies_sys_act - jiffies_sys_ant

            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                stat = procfs.leer_stat(pid)
                status = procfs.leer_status(pid)
                cmdline = procfs.leer_cmdline(pid)

                if stat and status:
                    jiffies_p_act = procfs.leer_jiffies_proceso(pid)
                    jiffies_p_ant = jiffies_proc_ant.get(pid, 0)
                    
                    delta_proc = jiffies_p_act - jiffies_p_ant
                    
                    cpu_percent = 0.0
                    if delta_sys > 0 and jiffies_p_ant > 0:
                        cores = os.cpu_count() or 1
                        cpu_percent = (delta_proc / delta_sys) * 100.0 * cores
                        
                    jiffies_proc_ant[pid] = jiffies_p_act
                    
                    rss_str = status.get("VmRSS", "0 kB").replace(" kB", "").strip()
                    rss_mb = int(rss_str) / 1024 if rss_str.isdigit() else 0.0
                    
                    estado = stat[2] if len(stat) > 2 else "?"
                    comando_final = cmdline if cmdline else str(status.get("Name", "Desconocido"))
                    
                    datos_resumen[pid] = {
                        "comando": comando_final,
                        "estado": str(estado),
                        "cpu": round(cpu_percent, 1),
                        "rss": round(rss_mb, 1),
                        "threads": str(status.get("Threads", "0")),
                        "usuario": str(status.get("User", "N/A")),
                        "ppid": str(status.get("PPid", "0"))
                    }

            snapshot["resumen"] = datos_resumen
            
            jiffies_sys_ant = jiffies_sys_act
            time.sleep(intervalo.value)

    except Exception as e:
        snapshot["resumen"] = {"ERROR": {"comando": f"CRASH: {e}", "estado": "?", "cpu": 0.0, "rss": 0.0, "threads": "0", "usuario": "", "ppid": ""}}
        time.sleep(intervalo.value)