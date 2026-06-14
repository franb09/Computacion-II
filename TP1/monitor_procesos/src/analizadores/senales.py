import time
import os
import procfs

def recolectar_senales(snapshot):
    while True:
        try:
            datos_senales = {}
            pids = [p for p in os.listdir('/proc') if p.isdigit()]
            
            for pid in pids:
                status = procfs.leer_status(pid)
                if not status:
                    continue
                
                sig_pnd = status.get("SigPnd", "0000000000000000")
                sig_blk = status.get("SigBlk", "0000000000000000")
                sig_ign = status.get("SigIgn", "0000000000000000")
                sig_cgt = status.get("SigCgt", "0000000000000000")
                if any(mask != "0000000000000000" for mask in [sig_blk, sig_ign, sig_cgt]):
                    datos_senales[pid] = {
                        "comando": str(status.get("Name", "Desconocido")),
                        "pendientes": sig_pnd,
                        "bloqueadas": sig_blk,
                        "ignoradas": sig_ign,
                        "capturadas": sig_cgt
                    }
            
            snapshot["senales"] = datos_senales
            time.sleep(3)
            
        except Exception as e:
            snapshot["senales"] = {"ERROR": {"comando": f"CRASH: {e}", "pendientes": "", "bloqueadas": "", "ignoradas": "", "capturadas": ""}}
            time.sleep(3)