from flask import Flask
import redis
import os

app = Flask(__name__)

redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

@app.route('/')
def index():
    contador = r.get('contador')
    if contador is None:
        contador = 0
    else:
        contador = int(contador.decode())
    return f"Contador actual: {contador}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
