import signal
import json

def configurar_senales(snapshot, intervalos, estado_ui):
    
    def manejador_sigusr1(signum, frame):
        try:
            data = dict(snapshot)
            with open("snapshot_dump.json", 'w') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def manejador_sighup(signum, frame):
        intervalos["1"].value = 2.0
        intervalos["2"].value = 3.0
        intervalos["3"].value = 5.0
        intervalos["4"].value = 3.0
        intervalos["5"].value = 3.0
        intervalos["6"].value = 2.0
        intervalos["7"].value = 2.0

    def manejador_sigusr2(signum, frame):
        estado_ui["modo_verbose"] = not estado_ui.get("modo_verbose", False)

    signal.signal(signal.SIGUSR1, manejador_sigusr1)
    signal.signal(signal.SIGHUP, manejador_sighup)
    signal.signal(signal.SIGUSR2, manejador_sigusr2)