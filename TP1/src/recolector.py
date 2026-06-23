import multiprocessing
from analizadores.resumen import recolectar_resumen
from analizadores.memoria import recolectar_memoria
from analizadores.fds import recolectar_fds
from analizadores.threads import recolectar_threads
from analizadores.senales import recolectar_senales
from analizadores.scheduling import recolectar_scheduling
from analizadores.sistema import recolectar_sistema

def iniciar_recolectores(snapshot, intervalos):
    procesos = []
    
    p_resumen = multiprocessing.Process(target=recolectar_resumen, args=(snapshot, intervalos["1"]), daemon=True)
    p_memoria = multiprocessing.Process(target=recolectar_memoria, args=(snapshot, intervalos["2"]), daemon=True)
    p_fds = multiprocessing.Process(target=recolectar_fds, args=(snapshot, intervalos["3"]), daemon=True)
    p_threads = multiprocessing.Process(target=recolectar_threads, args=(snapshot, intervalos["4"]), daemon=True)
    p_senales = multiprocessing.Process(target=recolectar_senales, args=(snapshot, intervalos["5"]), daemon=True)
    p_scheduling = multiprocessing.Process(target=recolectar_scheduling, args=(snapshot, intervalos["6"]), daemon=True)
    p_sistema = multiprocessing.Process(target=recolectar_sistema, args=(snapshot, intervalos["7"]), daemon=True)

    for p in [p_resumen, p_memoria, p_fds, p_threads, p_senales, p_scheduling, p_sistema]:
        p.start()
        procesos.append(p)
        
    return procesos