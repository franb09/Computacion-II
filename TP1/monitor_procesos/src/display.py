from rich.table import Table
from rich.panel import Panel
from rich.align import Align

def generar_tabla_resumen(resumen_actual):
    tabla = Table(show_header=True, header_style="bold cyan", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=30)
    tabla.add_column("ESTADO", justify="center", width=6)
    tabla.add_column("CPU %", justify="right", style="green", width=6)
    tabla.add_column("MEM (MB)", justify="right", style="yellow", width=8)
    tabla.add_column("THREADS", justify="right", width=7)
    procesos_ordenados = sorted(
        resumen_actual.items(), 
        key=lambda x: float(x[1].get('cpu', 0)) if isinstance(x[1], dict) else -1,
        reverse=True
    )[:10]

    for pid, datos in procesos_ordenados:
        tabla.add_row(
            str(pid),
            str(datos.get('comando', ''))[:30],
            str(datos.get('estado', '')),
            f"{datos.get('cpu', 0):.1f}",
            f"{datos.get('rss', 0):.1f}",
            str(datos.get('threads', '0'))
        )

    panel = Panel(Align.center(tabla),title="[bold magenta]Monitor de Procesos - Vista Resumen[/bold magenta]",subtitle="[dim]Presioná Q para salir[/dim]",border_style="blue")
    
    return panel

def generar_tabla_memoria(memoria_actual):
    tabla = Table(show_header=True, header_style="bold magenta", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("VmSize", justify="right")
    tabla.add_column("VmRSS", justify="right", style="green")
    tabla.add_column("VmData", justify="right")
    tabla.add_column("VmStk", justify="right")
    tabla.add_column("VmSwap", justify="right", style="red")
    tabla.add_column("Min/Maj Faults", justify="right")

    procesos_ordenados = sorted(
        memoria_actual.items(), 
        key=lambda x: int(x[1].get('vmrss', 0)) if isinstance(x[1], dict) and str(x[1].get('vmrss', 0)).isdigit() else -1,
        reverse=True
    )[:12]

    for pid, datos in procesos_ordenados:
        faults = f"{datos.get('minflt', '0')}/{datos.get('majflt', '0')}"
        tabla.add_row(
            str(pid),
            str(datos.get('comando', ''))[:20],
            f"{datos.get('vmsize', '0')} kB",
            f"{datos.get('vmrss', '0')} kB",
            f"{datos.get('vmdata', '0')} kB",
            f"{datos.get('vmstk', '0')} kB",
            f"{datos.get('vmswap', '0')} kB",
            faults
        )
    
    return Panel(Align.center(tabla), title="[bold magenta]Monitor de Procesos - Vista Memoria[/bold magenta]", border_style="magenta",subtitle="[dim]Presioná Q para salir[/dim]")

def generar_tabla_fds(fds_actual):
    tabla = Table(show_header=True, header_style="bold yellow", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("TOTAL FDs", justify="right", style="cyan", width=10)
    tabla.add_column("DESTINOS ABIERTOS (Muestra)", style="green")

    procesos_ordenados = sorted(
        fds_actual.items(), 
        key=lambda x: int(x[1].get('total_fds', 0)) if isinstance(x[1], dict) else -1,
        reverse=True
    )[:12]

    for pid, datos in procesos_ordenados:
        tabla.add_row(
            str(pid),
            str(datos.get('comando', ''))[:20],
            str(datos.get('total_fds', '0')),
            str(datos.get('ejemplos', ''))
        )
    
    return Panel(Align.center(tabla), title="[bold yellow]Monitor de Procesos - Vista FDs[/bold yellow]", border_style="yellow",subtitle="[dim]Presioná Q para salir[/dim]")

def generar_tabla_threads(threads_actual):
    tabla = Table(show_header=True, header_style="bold blue", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("TOTAL THREADS", justify="right", style="cyan", width=14)
    tabla.add_column("MUESTRA HILOS (TID:[Est] Nombre)", style="green")

    procesos_ordenados = sorted(
        threads_actual.items(), 
        key=lambda x: int(x[1].get('total_threads', 0)) if isinstance(x[1], dict) else -1,
        reverse=True
    )[:12]

    for pid, datos in procesos_ordenados:
        tabla.add_row(
            str(pid),
            str(datos.get('comando', ''))[:20],
            str(datos.get('total_threads', '0')),
            str(datos.get('ejemplos', ''))
        )
    
    return Panel(Align.center(tabla), title="[bold blue]Monitor de Procesos - Vista Threads[/bold blue]", border_style="blue", subtitle="[dim]Presioná Q para salir[/dim]")

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

    return Panel(Align.center(tabla), title="[bold green]Monitor de Procesos - Vista del Sistema Global[/bold green]", border_style="green",padding=(2, 2), subtitle="[dim]Presioná Q para salir[/dim]")

def generar_tabla_senales(senales_actual):
    tabla = Table(show_header=True, header_style="bold red", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("PENDIENTES", justify="center")
    tabla.add_column("BLOQUEADAS", justify="center", style="yellow")
    tabla.add_column("IGNORADAS", justify="center", style="dim")
    tabla.add_column("CAPTURADAS", justify="center", style="green")

    procesos_ordenados = sorted(
        senales_actual.items(), 
        key=lambda x: int(x[0]) if str(x[0]).isdigit() else -1
    )[:12] 

    for pid, datos in procesos_ordenados:
        tabla.add_row(
            str(pid),
            str(datos.get('comando', ''))[:20],
            str(datos.get('pendientes', '')),
            str(datos.get('bloqueadas', '')),
            str(datos.get('ignoradas', '')),
            str(datos.get('capturadas', ''))
        )
    
    return Panel(Align.center(tabla), title="[bold red]Monitor de Procesos - Vista Señales (Máscaras Hex)[/bold red]", border_style="red", subtitle="[dim]Presioná Q para salir[/dim]")

def generar_tabla_scheduling(sched_actual):
    tabla = Table(show_header=True, header_style="bold cyan", expand=True)
    tabla.add_column("PID", style="dim", width=6)
    tabla.add_column("COMANDO", width=20)
    tabla.add_column("PRIORIDAD", justify="center")
    tabla.add_column("NICE", justify="center", style="yellow")
    tabla.add_column("THREADS", justify="center", style="green")
    tabla.add_column("CPU CORE", justify="center", style="red")

    procesos_ordenados = sorted(
        sched_actual.items(), 
        key=lambda x: int(x[0]) if str(x[0]).isdigit() else -1
    )[:12]

    for pid, datos in procesos_ordenados:
        tabla.add_row(
            str(pid),
            str(datos.get('comando', ''))[:20],
            str(datos.get('prioridad', '')),
            str(datos.get('nice', '')),
            str(datos.get('threads', '')),
            str(datos.get('core', ''))
        )
    
    return Panel(Align.center(tabla), title="[bold cyan]Monitor de Procesos - Vista Scheduling[/bold cyan]", border_style="cyan", subtitle="[dim]Presioná Q para salir[/dim]")