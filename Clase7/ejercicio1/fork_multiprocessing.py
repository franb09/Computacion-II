import os
import multiprocessing

def tarea_hijo():
    print(f"PID hijo {os.getpid()}")
    os.execl("/bin/ls", "ls", "-l", "/home")

if __name__ == '__main__':
    print(f"PID padre {os.getpid()}")
    
    proceso = multiprocessing.Process(target=tarea_hijo)
    
    proceso.start()
    
    proceso.join()
    
    print(f"Terminó el código {os.getpid()}")