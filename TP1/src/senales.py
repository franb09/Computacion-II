import signal
import os

def configurar_senales():
    pipe_r, pipe_w = os.pipe()
    os.set_blocking(pipe_r, False) 

    def handler_sigusr1(signum, frame): os.write(pipe_w, b'1')
    def handler_sighup(signum, frame):  os.write(pipe_w, b'H')
    def handler_sigusr2(signum, frame): os.write(pipe_w, b'2')
    def handler_sigint(signum, frame):  os.write(pipe_w, b'I')
    def handler_sigterm(signum, frame): os.write(pipe_w, b'T')

    # Ahora si registro las 5 señales
    signal.signal(signal.SIGUSR1, handler_sigusr1)
    signal.signal(signal.SIGHUP, handler_sighup)
    signal.signal(signal.SIGUSR2, handler_sigusr2)
    signal.signal(signal.SIGINT, handler_sigint)
    signal.signal(signal.SIGTERM, handler_sigterm)

    return pipe_r 

#Cambie toda esta parte del código para que use el self-pipe y no haga nada que no sea async-signal-safe en los handlers. 
#Ahora el main.py puede leer del pipe y procesar las señales de forma segura. 