# data_generation.py

import json
import time
import uuid
import random
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

# vehicle identity
VEHICLE_UUID = str(uuid.uuid4())
VEHICLE_TYPE = random.choice(["diesel", "petrol", "ev"])

topic = f"fleet/{VEHICLE_UUID}/telemetry"

client = mqtt.Client()
client.connect(BROKER, PORT, 60)

speed = 0
odometer = 10000
fuel = 100
battery = 100

print("Vehicle:", VEHICLE_UUID, VEHICLE_TYPE)

while True:
    # smooth movement
    if speed == 0:
        if random.random() < 0.3:
            speed = random.randint(5, 15)
    else:
        move = random.randint(-5, 8)
        speed = speed + move

        if speed < 0:
            speed = 0
        if speed > 120:
            speed = 120

    rpm = speed * random.randint(25, 35)

    # km per second
    odometer += speed / 3600

    # consumption
    if VEHICLE_TYPE in ["diesel", "petrol"]:
        fuel = max(0, fuel - speed * 0.0005)
    else:
        battery = max(0, battery - speed * 0.0007)

    payload = {
        "uuid": VEHICLE_UUID,
        "vehicle_type": VEHICLE_TYPE,
        "timestamp": datetime.utcnow().isoformat(),
        "rpm": int(rpm),
        "speed": int(speed),
        "odometer": round(odometer, 3),
        "fuel_level": round(fuel, 2),
        "battery_soc": round(battery, 2),
        "air_pressure": random.randint(30, 35)
    }

    client.publish(topic, json.dumps(payload))
    print("Sent:", payload)

    time.sleep(1)
