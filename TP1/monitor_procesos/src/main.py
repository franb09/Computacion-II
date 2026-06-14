import multiprocessing
import threading
import time
import sys
import tty
import termios
import signal
import json
import os
from analizadores.resumen import recolectar_resumen
from analizadores.memoria import recolectar_memoria
from analizadores.fds import recolectar_fds
from analizadores.threads import recolectar_threads
from analizadores.sistema import recolectar_sistema
from analizadores.senales import recolectar_senales
from analizadores.scheduling import recolectar_scheduling
from display import (
    generar_tabla_resumen, 
    generar_tabla_memoria, 
    generar_tabla_fds, 
    generar_tabla_threads, 
    generar_vista_sistema, 
    generar_tabla_senales, 
    generar_tabla_scheduling
)
from rich.live import Live

vista_activa = "1"
corriendo = True

def capturar_tecla():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def hilo_teclado():
    global vista_activa, corriendo
    while corriendo:
        tecla = capturar_tecla().lower()
        if tecla == 'q':
            corriendo = False
        elif tecla in ['1', '2', '3', '4', '5', '6', '7', 'r', 'm', 'f', 't', 's', 'p', 'g']:
            mapeo_letras = {'r':'1', 'm':'2', 'f':'3', 't':'4', 's':'5', 'p':'6', 'g':'7'}
            vista_activa = mapeo_letras.get(tecla, tecla)

def main():
    global corriendo, vista_activa
    
    manager = multiprocessing.Manager()
    snapshot = manager.dict()
    snapshot["resumen"] = {}
    snapshot["memoria"] = {}
    snapshot["fds"] = {}
    snapshot["threads"] = {}
    snapshot["sistema"] = {}
    snapshot["senales"] = {}
    snapshot["scheduling"] = {}

    def manejador_sigusr1(signum, frame):
        try:
            data = dict(snapshot)
            with open("snapshot_dump.json", 'w') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
            
    signal.signal(signal.SIGUSR1, manejador_sigusr1)

    p_resumen = multiprocessing.Process(target=recolectar_resumen, args=(snapshot,), daemon=True)
    p_memoria = multiprocessing.Process(target=recolectar_memoria, args=(snapshot,), daemon=True)
    p_fds = multiprocessing.Process(target=recolectar_fds, args=(snapshot,), daemon=True)
    p_threads = multiprocessing.Process(target=recolectar_threads, args=(snapshot,), daemon=True)
    p_sistema = multiprocessing.Process(target=recolectar_sistema, args=(snapshot,), daemon=True)
    p_senales = multiprocessing.Process(target=recolectar_senales, args=(snapshot,), daemon=True)
    p_scheduling = multiprocessing.Process(target=recolectar_scheduling, args=(snapshot,), daemon=True)

    p_resumen.start()
    p_memoria.start()
    p_fds.start()
    p_threads.start()
    p_sistema.start()
    p_senales.start()
    p_scheduling.start()

    t_teclado = threading.Thread(target=hilo_teclado, daemon=True)
    t_teclado.start()

    try:
        with Live(generar_tabla_resumen(snapshot.get("resumen", {})), refresh_per_second=2, screen=True) as live:
            while corriendo:
                if vista_activa == "1":
                    tabla = generar_tabla_resumen(snapshot.get("resumen", {}))
                elif vista_activa == "2":
                    tabla = generar_tabla_memoria(snapshot.get("memoria", {}))
                elif vista_activa == "3":
                    tabla = generar_tabla_fds(snapshot.get("fds", {}))
                elif vista_activa == "4":
                    tabla = generar_tabla_threads(snapshot.get("threads", {}))
                elif vista_activa == "5":
                    tabla = generar_tabla_senales(snapshot.get("senales", {}))
                elif vista_activa == "6":
                    tabla = generar_tabla_scheduling(snapshot.get("scheduling", {}))
                elif vista_activa == "7":
                    tabla = generar_vista_sistema(snapshot.get("sistema", {}))
                else:
                    from rich.panel import Panel
                    tabla = Panel(f"Vista {vista_activa} en construcción.", title=f"Monitor - Vista {vista_activa}")

                live.update(tabla)
                time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        print("\nApagando el monitor de forma limpia...")
        for p in [p_resumen, p_memoria, p_fds, p_threads, p_sistema, p_senales, p_scheduling]:
            p.terminate()
            p.join()
        sys.exit(0)

if __name__ == "__main__":
    main()