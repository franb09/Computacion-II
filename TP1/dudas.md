## Duda sobre la ejecucion del proyecto:
En el repositorio esta puesto que es obligatorio que debe de correrse con 
```bash
docker compose up --build
```
El problema de este comando es que  esta diseñado para servicios en background. Hace que se inyecten prefijos en la salida (por ej: monitor-1) y no enlaza el flujo de entrada (stdin) de forma directa, por lo cual rompe el renderizado de la libreria e impide capturar los atajos del teclado pedido.
Por lo que, tuve que ejecutar siempre el TP con 
```bash
docker compose run --rm monitor
```
para que se inicien los contenedores interactivos con las interfaces TUI.
Mi duda es justamente esta, no se si es correcto el procedimiento de ejecutado. Quizas hay algo que estoy haciendo mal y no me he dado cuenta, pero es la vuelta que le encontre para poder ejecutar el proyecto de manera correcta.