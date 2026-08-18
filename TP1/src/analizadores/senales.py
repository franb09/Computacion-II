import os
import time
import signal
import procfs

#Se decodifico todo a nombres legibles, usando la libreria signal.Signals


MAPA_SENALES = {sig.value: sig.name.replace("SIG", "") for sig in signal.Signals}

def decodificar_mascara(mascara_hex):
    if not mascara_hex or mascara_hex == "0000000000000000":
        return "-"
    
    try:
        mascara_int = int(mascara_hex, 16)
        nombres = []
        
        for i in range(64):
            if mascara_int & (1 << i):
                numero_senal = i + 1 
                if numero_senal in MAPA_SENALES:
                    nombres.append(MAPA_SENALES[numero_senal])
                else:
                    nombres.append(str(numero_senal))
                    
        return ",".join(nombres) if nombres else "-"
    except ValueError:
        return mascara_hex

def recolectar_senales(snapshot, intervalo):
    try:
        while True:
            datos_senales = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                status = procfs.leer_status(pid)
                if status:
                    datos_senales[pid] = {
                        "comando": status.get("Name", "Desconocido"),
                        "pendientes": decodificar_mascara(status.get("SigPnd", "0000000000000000")),
                        "bloqueadas": decodificar_mascara(status.get("SigBlk", "0000000000000000")),
                        "ignoradas": decodificar_mascara(status.get("SigIgn", "0000000000000000")),
                        "capturadas": decodificar_mascara(status.get("SigCgt", "0000000000000000"))
                    }
                    
            snapshot["senales"] = datos_senales
            time.sleep(intervalo.value)
            
    except Exception as e:
        snapshot["senales"] = {"ERROR": {"comando": f"CRASH: {e}", "pendientes": "-", "bloqueadas": "-", "ignoradas": "-", "capturadas": "-"}}
        time.sleep(intervalo.value)