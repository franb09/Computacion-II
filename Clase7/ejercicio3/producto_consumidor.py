import multiprocessing
import time
import random

def productor(cola):
    print("[Productor] Iniciando producción...")
    for i in range(1, 11):
        item = f"Producto-{i}"
        print(f"[Productor] Generando {item}")
        cola.put(item)
        
        time.sleep(random.uniform(0.1, 0.3))
        
    print("[Productor] Producción finalizada. Enviando señal de fin (None).")
    cola.put(None)

def consumidor(cola):
    print("[Consumidor] Esperando productos...")
    while True:
        item = cola.get()
        
        if item is None:
            print("[Consumidor] Señal de fin recibida. Terminando proceso.")
            break
            
        print(f"[Consumidor] Procesando {item}")
        
        time.sleep(random.uniform(0.2, 0.5))

if __name__ == '__main__':
    cola = multiprocessing.Queue()
    p_productor = multiprocessing.Process(target=productor, args=(cola,))
    p_consumidor = multiprocessing.Process(target=consumidor, args=(cola,))
    p_productor.start()
    p_consumidor.start()

    p_productor.join()
    p_consumidor.join()
    
    print("-" * 30)
    print("Programa finalizado con éxito.")