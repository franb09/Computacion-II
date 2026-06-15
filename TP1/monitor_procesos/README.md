#TP 1 de computación II
**Alumno:** Franco Berardo
**Carrera:** Ing. en computación

##Descripción:
Este trabajo práctico trata de la elaboración de una herramienta de monitorio del sistema operativo utilizando python. Permite ver en tiempo
real el estado de los procesos, el consumo de memoria, la gestión de hilos, entre otras cosas.

##Requisitos y Ejecución
El proyecto está completamente dockerizado. Para ejecutarlo, es necesario tener instalado Docker y Docker Compose en un entorno Linux.
Para iniciar el monitor de forma interactiva (con soporte para teclado completo), ejecutar el siguiente comando en la raíz del proyecto:
```bash
docker compose run --rm monitor
