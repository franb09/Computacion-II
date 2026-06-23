import multiprocessing
import threading
import time
import sys
import tty
import termios
import os

from display import (
    generar_tabla_resumen, 
    generar_tabla_memoria, 
    generar_tabla_fds, 
    generar_tabla_threads, 
    generar_vista_sistema, 
    generar_tabla_senales, 
    generar_tabla_scheduling,
    generar_panel_ayuda
)
from senales import configurar_senales
from recolector import iniciar_recolectores
from rich.live import Live
from rich.panel import Panel

vista_activa = "1"
corriendo = True

intervalos = {
    "1": multiprocessing.Value('d', 2.0),
    "2": multiprocessing.Value('d', 3.0),
    "3": multiprocessing.Value('d', 5.0),
    "4": multiprocessing.Value('d', 3.0),
    "5": multiprocessing.Value('d', 3.0),
    "6": multiprocessing.Value('d', 2.0),
    "7": multiprocessing.Value('d', 2.0),
}

estado_ui = {
    "fila_seleccionada": 0,
    "pineado": None,
    "filtro_cmd": "",
    "filtro_usr": "",
    "orden": "default", 
    "input_activo": None, 
    "buffer": "",
    "ayuda": False,
    "pid_en_fila": None 
}

def capturar_tecla():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b': # Secuencia de escape
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            if ch2 == '[':
                if ch3 == 'A': return 'up'
                if ch3 == 'B': return 'down'
        elif ch in ('\n', '\r'): return 'enter'
        elif ch in ('\x7f', '\b'): return 'backspace' 
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def hilo_teclado():
    global vista_activa, corriendo, estado_ui
    while corriendo:
        tecla = capturar_tecla()
        
        if estado_ui["input_activo"]:
            if tecla == 'enter':
                if estado_ui["input_activo"] == 'cmd':
                    estado_ui["filtro_cmd"] = estado_ui["buffer"]
                else:
                    estado_ui["filtro_usr"] = estado_ui["buffer"]
                estado_ui["input_activo"] = None
                estado_ui["buffer"] = ""
            elif tecla == 'backspace':
                estado_ui["buffer"] = estado_ui["buffer"][:-1]
            elif tecla == '\x1b': 
                estado_ui["input_activo"] = None
                estado_ui["buffer"] = ""
            elif len(tecla) == 1:
                estado_ui["buffer"] += tecla
            continue

        if not isinstance(tecla, str): continue
        tecla_lower = tecla.lower()

        if tecla_lower == 'q':
            corriendo = False
        elif tecla_lower in ['1', '2', '3', '4', '5', '6', '7', 'r', 'm', 'f', 't', 's', 'p', 'g']:
            mapeo_letras = {'r':'1', 'm':'2', 'f':'3', 't':'4', 's':'5', 'p':'6', 'g':'7'}
            vista_activa = mapeo_letras.get(tecla_lower, tecla_lower)
            estado_ui["fila_seleccionada"] = 0
        elif tecla_lower == '+':
            if vista_activa in intervalos:
                intervalos[vista_activa].value = max(0.5, intervalos[vista_activa].value - 0.5)
        elif tecla_lower == '-':
            if vista_activa in intervalos:
                intervalos[vista_activa].value += 0.5
        elif tecla == 'up':
            estado_ui["fila_seleccionada"] = max(0, estado_ui["fila_seleccionada"] - 1)
        elif tecla == 'down':
            estado_ui["fila_seleccionada"] += 1
        elif tecla == 'enter':
            if estado_ui["pineado"] == estado_ui["pid_en_fila"]:
                estado_ui["pineado"] = None
            else:
                estado_ui["pineado"] = estado_ui["pid_en_fila"]
        elif tecla == '/':
            estado_ui["input_activo"] = 'cmd'
        elif tecla == 'u':
            estado_ui["input_activo"] = 'usr'
        elif tecla_lower == 'c':
            ordenes = ['default', 'pid', 'cpu', 'rss']
            idx = ordenes.index(estado_ui["orden"])
            estado_ui["orden"] = ordenes[(idx + 1) % len(ordenes)]
        elif tecla_lower in ['h', '?']:
            estado_ui["ayuda"] = not estado_ui["ayuda"]

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

    configurar_senales(snapshot, intervalos, estado_ui)

    procesos_activos = iniciar_recolectores(snapshot, intervalos)

    t_teclado = threading.Thread(target=hilo_teclado, daemon=True)
    t_teclado.start()

    try:
        with Live(generar_tabla_resumen(snapshot.get("resumen", {}), estado_ui), refresh_per_second=5, screen=True) as live:
            while corriendo:
                if estado_ui["ayuda"]:
                    pantalla = generar_panel_ayuda()
                else:
                    if vista_activa == "1":
                        pantalla = generar_tabla_resumen(snapshot.get("resumen", {}), estado_ui)
                    elif vista_activa == "2":
                        pantalla = generar_tabla_memoria(snapshot.get("memoria", {}), estado_ui)
                    elif vista_activa == "3":
                        pantalla = generar_tabla_fds(snapshot.get("fds", {}), estado_ui)
                    elif vista_activa == "4":
                        pantalla = generar_tabla_threads(snapshot.get("threads", {}), estado_ui)
                    elif vista_activa == "5":
                        pantalla = generar_tabla_senales(snapshot.get("senales", {}), estado_ui)
                    elif vista_activa == "6":
                        pantalla = generar_tabla_scheduling(snapshot.get("scheduling", {}), estado_ui)
                    elif vista_activa == "7":
                        pantalla = generar_vista_sistema(snapshot.get("sistema", {}))
                    else:
                        pantalla = Panel(f"Vista {vista_activa} en construcción.", title=f"Monitor")
                    
                    if estado_ui["input_activo"]:
                        tipo = "Comando" if estado_ui["input_activo"] == 'cmd' else "Usuario"
                        pantalla.title = pantalla.title + f" | [bold green]Filtrar {tipo}: {estado_ui['buffer']}█[/bold green]"
                    else:
                        pantalla.title = pantalla.title + f" [dim](Refresco: {intervalos[vista_activa].value:.1f}s)[/dim]"
                    pantalla.subtitle = "[dim]Presione 'q' para salir | 'h' para ayuda[/dim]"

                live.update(pantalla)
                time.sleep(0.1) 

    except KeyboardInterrupt:
        pass
    finally:
        print("\nApagando el monitor de forma limpia...")
        for p in procesos_activos:
            p.terminate()
            p.join()
        sys.exit(0)

if __name__ == "__main__":
    main()