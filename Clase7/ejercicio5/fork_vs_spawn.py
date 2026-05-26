import multiprocessing as mp
import time

def tarea_vacia():
    pass

def medir_tiempo_creacion(metodo, num_procesos=100):
    ctx = mp.get_context(metodo)
    procesos = []
    
    inicio = time.time()
    
    for _ in range(num_procesos):
        p = ctx.Process(target=tarea_vacia)
        procesos.append(p)
        p.start()
        
    for p in procesos:
        p.join()
        
    fin = time.time()
    return fin - inicio

if __name__ == '__main__':
    print("Midiendo tiempo de creación de 100 procesos...\n")
    
    tiempo_fork = medir_tiempo_creacion('fork')
    print(f"Tiempo total con 'fork':  {tiempo_fork:.4f} segundos")
    
    tiempo_spawn = medir_tiempo_creacion('spawn')
    print(f"Tiempo total con 'spawn': {tiempo_spawn:.4f} segundos")
    
    diferencia = tiempo_spawn / tiempo_fork
    print(f"\nConclusión: 'spawn' fue aprox. {diferencia:.1f} veces más lento que 'fork'.")