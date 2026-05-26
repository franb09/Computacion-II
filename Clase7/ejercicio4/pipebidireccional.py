import multiprocessing
import time

def hijo_ping_pong(conn_hijo):
    for i in range(1, 6):
        mensaje_recibido = conn_hijo.recv()
        print(f"[Hijo] Recibió: {mensaje_recibido}")
        
        time.sleep(0.5) 
        mensaje_respuesta = f"Pong {i}"
        print(f"[Hijo] Enviando: {mensaje_respuesta}")
        conn_hijo.send(mensaje_respuesta)
        
    conn_hijo.close()

if __name__ == '__main__':
    conn_padre, conn_hijo = multiprocessing.Pipe()
    p_hijo = multiprocessing.Process(target=hijo_ping_pong, args=(conn_hijo,))
    p_hijo.start()
    
    for i in range(1, 6):
        mensaje = f"Ping {i}"
        print(f"[Padre] Enviando: {mensaje}")
        conn_padre.send(mensaje)
        
        respuesta = conn_padre.recv()
        print(f"[Padre] Recibió: {respuesta}\n")
        
        time.sleep(0.5)
        
    p_hijo.join()
    
    conn_padre.close()
    
    print("-" * 30)
    print("Partida de ping pong finalizada.")