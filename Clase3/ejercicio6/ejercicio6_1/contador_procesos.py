#!/usr/bin/env python3
"""
Ejercicio 6.1: Contador de procesos
Muestra cuántos procesos están corriendo en el sistema.
"""
import os


def contar_procesos():
    """
    Cuenta los procesos activos en el sistema.
    Los PIDs son directorios numéricos en /proc/
    """
    proc_dir = "/proc"
    contador = 0
    
    try:
        entries = os.listdir(proc_dir)
        
        for entry in entries:
            # Verificar si el nombre es un número (PID)
            if entry.isdigit():
                # Verificar que el directorio existe y es accesible
                pid_path = os.path.join(proc_dir, entry)
                if os.path.isdir(pid_path):
                    contador += 1
    except OSError as e:
        print(f"Error al acceder a {proc_dir}: {e}")
        return None
    
    return contador


def main():
    total = contar_procesos()
    
    if total is not None:
        print(f"Procesos corriendo en el sistema: {total}")
    else:
        print("No se pudo contar los procesos")


if __name__ == "__main__":
    main()
