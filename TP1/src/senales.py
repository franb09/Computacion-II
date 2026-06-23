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
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                for k in intervalos:
                    if k in config:
                        intervalos[k].value = float(config[k])
        except Exception:
            defaults = {"1": 2.0, "2": 3.0, "3": 5.0, "4": 3.0, "5": 3.0, "6": 2.0, "7": 2.0}
            for k, v in defaults.items():
                intervalos[k].value = v

    def manejador_sigusr2(signum, frame):
        estado_ui["modo_verbose"] = not estado_ui.get("modo_verbose", False)

    signal.signal(signal.SIGUSR1, manejador_sigusr1)
    signal.signal(signal.SIGHUP, manejador_sighup)
    signal.signal(signal.SIGUSR2, manejador_sigusr2)