import redis
import os
import time

redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

print(f"Conectando a Redis en {redis_host}...")

# Esperar a que Redis esté disponible
while True:
    try:
        r.ping()
        print("Conexión a Redis exitosa.")
        break
    except redis.ConnectionError:
        print("Esperando a Redis...")
        time.sleep(1)

while True:
    r.incr('contador')
    contador = r.get('contador')
    print(f"Contador incrementado a: {int(contador.decode())}")
    time.sleep(1)
