#!/usr/bin/env python3
"""
Ejercicio 6.3: Árbol de procesos
Implementa una versión simplificada de pstree que muestre la jerarquía de procesos.
"""
import os
import sys


def obtener_procesos():
    """
    Lee /proc y retorna un diccionario con la información de procesos.
    Retorna: {pid: {"ppid": parent_pid, "nombre": nombre_proceso}}
    """
    procesos = {}
    
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                pid = int(entry)
                proc_path = f"/proc/{pid}"
                
                try:
                    # Obtener nombre del proceso
                    with open(f"{proc_path}/comm", "r") as f:
                        nombre = f.read().strip()
                    
                    # Obtener PID del padre
                    with open(f"{proc_path}/status", "r") as f:
                        ppid = None
                        for line in f:
                            if line.startswith("PPid:"):
                                ppid = int(line.split()[1])
                                break
                    
                    if ppid is not None:
                        procesos[pid] = {"ppid": ppid, "nombre": nombre}
                except (FileNotFoundError, OSError):
                    pass
    except OSError as e:
        print(f"Error al leer /proc: {e}")
    
    return procesos


def mostrar_arbol(pid, procesos, prefijo="", es_ultimo=True):
    """
    Muestra el árbol de procesos recursivamente.
    
    Args:
        pid: PID del proceso raíz del subárbol
        procesos: diccionario con información de procesos
        prefijo: prefijo para la indentación (líneas del árbol)
        es_ultimo: si es el último hijo del padre
    """
    if pid not in procesos:
        return
    
    info = procesos[pid]
    nombre = info["nombre"]
    
    # Mostrar información del proceso
    if pid == 1:
        print(f"init({pid})")
    else:
        # Determinar caracteres de conexión
        if prefijo == "":
            conecta = ""
        else:
            conecta = "└── " if es_ultimo else "├── "
        
        print(f"{prefijo}{conecta}{nombre}({pid})")
    
    # Encontrar hijos de este proceso
    hijos = [p for p, info in procesos.items() if info["ppid"] == pid]
    
    if not hijos:
        return
    
    # Ordenar los hijos por PID
    hijos.sort()
    
    # Mostrar cada hijo
    for i, hijo_pid in enumerate(hijos):
        es_ultimo_hijo = (i == len(hijos) - 1)
        
        if prefijo == "":
            nuevo_prefijo = ""
        else:
            nuevo_prefijo = prefijo + ("    " if es_ultimo else "│   ")
        
        mostrar_arbol(hijo_pid, procesos, nuevo_prefijo, es_ultimo_hijo)


def main():
    print("=== Árbol de Procesos ===\n")
    
    procesos = obtener_procesos()
    
    if not procesos:
        print("No se pudo obtener información de los procesos")
        sys.exit(1)
    
    # Mostrar el árbol completo comenzando por init (PID 1)
    if 1 in procesos:
        mostrar_arbol(1, procesos)
    else:
        print("No se encontró el proceso init (PID 1)")
        sys.exit(1)
    
    print(f"\nTotal de procesos: {len(procesos)}")


if __name__ == "__main__":
    main()
