#!/usr/bin/env python3
"""
Ejercicio 6.2: Información de proceso
Dado un PID, muestra información del proceso leyendo archivos de /proc/<PID>/
"""
import os
import sys


def obtener_info_proceso(pid):
    """
    Obtiene información del proceso con el PID especificado.
    Lee archivos de /proc/<pid>/
    """
    proc_path = f"/proc/{pid}"
    
    if not os.path.exists(proc_path):
        print(f"Error: El proceso con PID {pid} no existe")
        return False
    
    print(f"=== Información del proceso {pid} ===\n")
    
    # 1. Comando completo (cmdline)
    try:
        with open(f"{proc_path}/cmdline", "r") as f:
            cmdline = f.read().replace("\x00", " ").strip()
            if cmdline:
                print(f"Comando: {cmdline}")
            else:
                print(f"Comando: [kernel thread]")
    except (FileNotFoundError, PermissionError) as e:
        print(f"Comando: [no disponible - {e}]")
    
    print()
    
    # 2. Información de estado (status)
    try:
        with open(f"{proc_path}/status", "r") as f:
            print("Estado del proceso:")
            for line in f:
                # Mostrar campos relevantes
                key = line.split(":")[0]
                if key in ["Name", "State", "PPid", "VmPeak", "VmRSS", "Threads", "FDSize"]:
                    print(f"  {line.rstrip()}")
    except (FileNotFoundError, PermissionError) as e:
        print(f"Estado: [no disponible - {e}]")
    
    print()
    
    # 3. File descriptors abiertos (fd/)
    try:
        fd_path = f"{proc_path}/fd"
        if os.path.exists(fd_path):
            fds = os.listdir(fd_path)
            print(f"File descriptors abiertos: {len(fds)}")
            print("  FD\tArchivo")
            for fd in sorted(fds):
                try:
                    link = os.readlink(os.path.join(fd_path, fd))
                    print(f"  {fd}\t{link}")
                except OSError:
                    print(f"  {fd}\t[no disponible]")
    except (FileNotFoundError, PermissionError) as e:
        print(f"File descriptors: [no disponible - {e}]")
    
    return True


def main():
    if len(sys.argv) != 2:
        print(f"Uso: {sys.argv[0]} <PID>")
        print("Ejemplo: {sys.argv[0]} 1234")
        sys.exit(1)
    
    try:
        pid = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' no es un PID válido (debe ser un número)")
        sys.exit(1)
    
    if not obtener_info_proceso(pid):
        sys.exit(1)


if __name__ == "__main__":
    main()
