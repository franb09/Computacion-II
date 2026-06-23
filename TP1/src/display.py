from rich.table import Table
from rich.panel import Panel
from rich.align import Align

def generar_panel_ayuda():
    tabla = Table(show_header=True, header_style="bold magenta", expand=True)
    tabla.add_column("Tecla")
    tabla.add_column("Acción")
    atajos = [
        ("1 - 7 o r/m/f/t/s/p/g", "Cambiar de vista"),
        ("↑ ↓", "Navegar por la lista de procesos"),
        ("Enter", "Pin del proceso seleccionado"),
        ("/", "Filtrar por nombre de comando"),
        ("u", "Filtrar por usuario"),
        ("c", "Toggle ordenamiento (CPU% / RSS / PID)"),
        ("+ / -", "Ajustar intervalo de la vista activa"),
        ("q", "Salir limpiamente"),
        ("h / ?", "Ayuda (cerrar esta pantalla)")
    ]
    for tecla, accion in atajos:
        tabla.add_row(f"[bold]{tecla}[/bold]", accion)
    return Panel(Align.center(tabla), title="[bold magenta]Ayuda - Atajos de Teclado[/bold magenta]", border_style="magenta")

def procesar_datos_ui(datos_dict, estado_ui, max_filas=12):
    filtrados = []
    for pid, info in datos_dict.items():
        if pid == "ERROR": continue
        cmd = str(info.get('comando', '')).lower()
        usr = str(info.get('usuario', '')).lower() 
        if estado_ui["filtro_cmd"] and estado_ui["filtro_cmd"].lower() not in cmd:
            continue
        if estado_ui["filtro_usr"] and estado_ui["filtro_usr"].lower() not in usr:
            continue
        filtrados.append((pid, info))
    
    def get_num(item, key):
        try: return float(item.get(key, 0.0))
        except: return 0.0

    if estado_ui["orden"] == "pid":
        filtrados.sort(key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)
    elif estado_ui["orden"] == "rss":
        filtrados.sort(key=lambda x: get_num(x[1], 'memoria'), reverse=True)
    else:
        filtrados.sort(key=lambda x: get_num(x[1], 'cpu'), reverse=True)
    
    lista_final = []
    pineado_item = None
    if estado_ui["pineado"]:
        for item in filtrados:
            if item[0] == estado_ui["pineado"]:
                pineado_item = item
                break
        if pineado_item:
            filtrados.remove(pineado_item)
            lista_final.append(pineado_item)

    lista_final.extend(filtrados)
    lista_final = lista_final[:max_filas]

    if len(lista_final) > 0:
        estado_ui["fila_seleccionada"] = max(0, min(estado_ui["fila_seleccionada"], len(lista_final) - 1))
        estado_ui["pid_en_fila"] = lista_final[estado_ui["fila_seleccionada"]][0]
    else:
        estado_ui["pid_en_fila"] = None
        estado_ui["fila_seleccionada"] = 0

    return lista_final


def generar_tabla_resumen(resumen_actual, estado_ui):
    tabla = Table(show_header=True, header_style="bold cyan", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("ESTADO", justify="center", width=8)
    tabla.add_column("CPU %", justify="right", style="green", width=8)
    tabla.add_column("MEM (MB)", justify="right", style="yellow", width=10)
    tabla.add_column("THREADS", justify="right", width=8)

    procesos_ordenados = procesar_datos_ui(resumen_actual, estado_ui)

    for idx, (pid, datos) in enumerate(procesos_ordenados):
        estilo = "on blue" if idx == estado_ui["fila_seleccionada"] else ""
        indicador_pid = f"📌 {pid}" if pid == estado_ui["pineado"] else pid

        tabla.add_row(
            indicador_pid,
            str(datos.get('comando', ''))[:20],
            str(datos.get('estado', '')),
            str(datos.get('cpu', '0.0')),
            str(datos.get('memoria', '0.0')),
            str(datos.get('threads', '0')),
            style=estilo
        )
    
    modo = f" [Orden: {estado_ui['orden'].upper()}]"
    return Panel(Align.center(tabla), title=f"[bold cyan]Monitor de Procesos - Vista Resumen{modo}[/bold cyan]", border_style="cyan")


def generar_tabla_memoria(memoria_actual, estado_ui):
    tabla = Table(show_header=True, header_style="bold magenta", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("VmSize", justify="right")
    tabla.add_column("VmRSS", justify="right", style="green")
    tabla.add_column("VmData", justify="right")
    tabla.add_column("VmStk", justify="right")
    tabla.add_column("VmSwap", justify="right", style="red")
    tabla.add_column("Min/Maj Faults", justify="right")

    procesos_ordenados = procesar_datos_ui(memoria_actual, estado_ui)

    for idx, (pid, datos) in enumerate(procesos_ordenados):
        estilo = "on blue" if idx == estado_ui["fila_seleccionada"] else ""
        indicador_pid = f"📌 {pid}" if pid == estado_ui["pineado"] else pid

        tabla.add_row(
            indicador_pid,
            str(datos.get('comando', ''))[:20],
            str(datos.get('vmsize', '0')),
            str(datos.get('vmrss', '0')),
            str(datos.get('vmdata', '0')),
            str(datos.get('vmstk', '0')),
            str(datos.get('vmswap', '0')),
            str(datos.get('faults', '0/0')),
            style=estilo
        )
    
    modo = f" [Orden: {estado_ui['orden'].upper()}]"
    return Panel(Align.center(tabla), title=f"[bold magenta]Monitor de Procesos - Vista Memoria{modo}[/bold magenta]", border_style="magenta")


def generar_tabla_fds(fds_actual, estado_ui):
    tabla = Table(show_header=True, header_style="bold yellow", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("TOTAL FDs", justify="right", style="cyan", width=10)
    tabla.add_column("DESTINOS ABIERTOS (Muestra)", style="green")

    procesos_ordenados = procesar_datos_ui(fds_actual, estado_ui)

    for idx, (pid, datos) in enumerate(procesos_ordenados):
        estilo = "on blue" if idx == estado_ui["fila_seleccionada"] else ""
        indicador_pid = f"📌 {pid}" if pid == estado_ui["pineado"] else pid

        tabla.add_row(
            indicador_pid,
            str(datos.get('comando', ''))[:20],
            str(datos.get('total_fds', '0')),
            str(datos.get('ejemplos', '')),
            style=estilo
        )
    
    modo = f" [Orden: {estado_ui['orden'].upper()}]"
    return Panel(Align.center(tabla), title=f"[bold yellow]Monitor de Procesos - Vista FDs{modo}[/bold yellow]", border_style="yellow")


def generar_tabla_threads(threads_actual, estado_ui):
    tabla = Table(show_header=True, header_style="bold blue", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("TOTAL THREADS", justify="right", style="cyan", width=14)
    tabla.add_column("MUESTRA HILOS", style="green")

    procesos_ordenados = procesar_datos_ui(threads_actual, estado_ui)

    for idx, (pid, datos) in enumerate(procesos_ordenados):
        estilo = "on blue" if idx == estado_ui["fila_seleccionada"] else ""
        indicador_pid = f"📌 {pid}" if pid == estado_ui["pineado"] else pid

        tabla.add_row(
            indicador_pid,
            str(datos.get('comando', ''))[:20],
            str(datos.get('total_threads', '0')),
            str(datos.get('ejemplos', '')),
            style=estilo
        )
    
    modo = f" [Orden: {estado_ui['orden'].upper()}]"
    return Panel(Align.center(tabla), title=f"[bold blue]Monitor de Procesos - Vista Threads{modo}[/bold blue]", border_style="blue")


def generar_tabla_senales(senales_actual, estado_ui):
    tabla = Table(show_header=True, header_style="bold red", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("PENDIENTES", justify="center")
    tabla.add_column("BLOQUEADAS", justify="center", style="yellow")
    tabla.add_column("IGNORADAS", justify="center", style="dim")
    tabla.add_column("CAPTURADAS", justify="center", style="green")

    procesos_ordenados = procesar_datos_ui(senales_actual, estado_ui)

    for idx, (pid, datos) in enumerate(procesos_ordenados):
        estilo = "on blue" if idx == estado_ui["fila_seleccionada"] else ""
        indicador_pid = f"📌 {pid}" if pid == estado_ui["pineado"] else pid

        tabla.add_row(
            indicador_pid,
            str(datos.get('comando', ''))[:20],
            str(datos.get('pendientes', '')),
            str(datos.get('bloqueadas', '')),
            str(datos.get('ignoradas', '')),
            str(datos.get('capturadas', '')),
            style=estilo
        )
    
    modo = f" [Orden: {estado_ui['orden'].upper()}]"
    return Panel(Align.center(tabla), title=f"[bold red]Monitor de Procesos - Vista Señales{modo}[/bold red]", border_style="red")


def generar_tabla_scheduling(sched_actual, estado_ui):
    tabla = Table(show_header=True, header_style="bold cyan", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("PRIORIDAD", justify="center")
    tabla.add_column("NICE", justify="center", style="yellow")
    tabla.add_column("THREADS", justify="center", style="green")
    tabla.add_column("CPU CORE", justify="center", style="red")

    procesos_ordenados = procesar_datos_ui(sched_actual, estado_ui)

    for idx, (pid, datos) in enumerate(procesos_ordenados):
        estilo = "on blue" if idx == estado_ui["fila_seleccionada"] else ""
        indicador_pid = f"📌 {pid}" if pid == estado_ui["pineado"] else pid

        tabla.add_row(
            indicador_pid,
            str(datos.get('comando', ''))[:20],
            str(datos.get('prioridad', '')),
            str(datos.get('nice', '')),
            str(datos.get('threads', '')),
            str(datos.get('core', '')),
            style=estilo
        )
    
    modo = f" [Orden: {estado_ui['orden'].upper()}]"
    return Panel(Align.center(tabla), title=f"[bold cyan]Monitor de Procesos - Vista Scheduling{modo}[/bold cyan]", border_style="cyan")


def generar_vista_sistema(sistema_actual):
    if "ERROR" in sistema_actual:
        return Panel(f"[red]Error leyendo sistema: {sistema_actual['ERROR']}[/red]")

    tabla = Table(show_header=False, expand=True, box=None)
    tabla.add_column("Métrica", style="bold cyan", width=30)
    tabla.add_column("Valor", style="green")

    load = " ".join(sistema_actual.get('loadavg', ["0.00", "0.00", "0.00"]))
    mem = sistema_actual.get('meminfo', {})
    mem_total = mem.get('MemTotal', '0 kB')
    mem_free = mem.get('MemAvailable', mem.get('MemFree', '0 kB'))
    uptime = sistema_actual.get('uptime', '0h 0m')

    tabla.add_row("Carga Media (1m, 5m, 15m):", load)
    tabla.add_row("Memoria RAM Total:", mem_total)
    tabla.add_row("Memoria RAM Disponible:", mem_free)
    tabla.add_row("Tiempo Encendido (Uptime):", uptime)

    return Panel(
        Align.center(tabla), 
        title="[bold green]Monitor de Procesos - Vista del Sistema Global[/bold green]", 
        border_style="green",
        padding=(2, 2)
    )