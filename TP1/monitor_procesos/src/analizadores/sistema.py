import time

def recolectar_sistema(snapshot, intervalo):

    while True:
        try:
            datos = {}
            
            with open('/proc/loadavg', 'r') as f:
                datos['loadavg'] = f.read().split()[:3]
            
            with open('/proc/meminfo', 'r') as f:
                mem = {}
                for linea in f:
                    if ':' in linea:
                        k, v = linea.split(':', 1)
                        mem[k.strip()] = v.strip()
                datos['meminfo'] = mem
            
            with open('/proc/uptime', 'r') as f:
                up_sec = float(f.read().split()[0])
                horas = int(up_sec // 3600)
                mins = int((up_sec % 3600) // 60)
                datos['uptime'] = f"{horas}h {mins}m"
            
            snapshot["sistema"] = datos
            time.sleep(intervalo.value)
            
        except Exception as e:
            snapshot["sistema"] = {"ERROR": str(e)}
            time.sleep(intervalo.value)