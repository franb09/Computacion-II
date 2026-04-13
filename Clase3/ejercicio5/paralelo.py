#!/usr/bin/env python3
"""
Ejecutor de comandos en paralelo.
Uso: python3 paralelo.py "cmd1" "cmd2" ...
"""
import os
import sys
import time


def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} comando1 [comando2 ...]")
        sys.exit(1)

    comandos = sys.argv[1:]
    inicio = time.time()
    
    # Diccionario para trackear PIDs y sus comandos
    procesos = {}  # {pid: comando}
    
    # Crear todos los procesos hijo
    for cmd in comandos:
        pid = os.fork()
        
        if pid == 0:  # Proceso hijo
            # Parsear comando y argumentos
            partes = cmd.split()
            programa = partes[0]
            args = partes[1:]
            
            try:
                os.execvp(programa, [programa] + args)
            except OSError as e:
                print(f"Error: {programa}: {e}")
                os._exit(127)
        else:  # Proceso padre
            procesos[pid] = cmd
            print(f"[{pid}] Iniciado: {cmd}")
    
    # Esperar a que todos los procesos terminen
    exitosos = 0
    fallidos = 0
    
    while procesos:
        pid, status = os.wait()
        codigo = os.WEXITSTATUS(status)
        cmd = procesos.pop(pid)
        print(f"[{pid}] Terminado: {cmd} (código: {codigo})")
        
        if codigo == 0:
            exitosos += 1
        else:
            fallidos += 1
    
    duracion = time.time() - inicio
    
    # Mostrar resumen
    print(f"\nResumen:")
    print(f"- Comandos ejecutados: {len(comandos)}")
    print(f"- Exitosos: {exitosos}")
    print(f"- Fallidos: {fallidos}")
    print(f"- Tiempo total: {duracion:.2f}s")


if __name__ == "__main__":
    main()
