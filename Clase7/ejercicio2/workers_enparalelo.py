import multiprocessing
import time
import random

def worker(id_worker):
    tiempo_espera = random.uniform(0.5, 2.0)
    print(f"Worker {id_worker} (PID: {multiprocessing.current_process().pid}) durmiendo {tiempo_espera:.2f} segs...")
    
    time.sleep(tiempo_espera)
    
    print(f"Worker {id_worker} terminó.")

if __name__ == '__main__':
    print("Iniciando programa principal...")
    
    tiempo_inicio = time.time()
    
    procesos = []
    
    for i in range(5):
        p = multiprocessing.Process(target=worker, args=(i,))
        procesos.append(p)
        p.start()
        
    for p in procesos:
        p.join()
        
    tiempo_fin = time.time()
    tiempo_total = tiempo_fin - tiempo_inicio
    
    print("-" * 30)
    print("Todos los workers finalizaron.")
    print(f"Tiempo total de ejecución: {tiempo_total:.2f} segundos.")