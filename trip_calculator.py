# trip_calculator.py

import json
from datetime import datetime
import paho.mqtt.client as mqtt
import uuid

BROKER = "localhost"
PORT = 1883

# memory
trips = {}
last_speed = {}
leaderboard = {}


# ---------------- TRIP START ----------------
def start_trip(data):
    return {
        "trip_id": str(uuid.uuid4()),
        "start_time": data["timestamp"],
        "start_odo": data["odometer"],
        "start_fuel": data.get("fuel_level"),
        "start_soc": data.get("battery_soc"),
        "speed_sum": 0,
        "speed_count": 0,
        "max_speed": 0,
        "harsh_brake": 0,
        "harsh_acc": 0
    }


# ---------------- TRIP END ----------------
def end_trip(vehicle_uuid, trip, data, client):
    distance = data["odometer"] - trip["start_odo"]
    avg_speed = trip["speed_sum"] / max(1, trip["speed_count"])

    # duration
    start = datetime.fromisoformat(trip["start_time"])
    end = datetime.fromisoformat(data["timestamp"])
    duration = (end - start).total_seconds()

    # ---------- DRIVER SCORE ----------
    score = 100
    score -= trip["harsh_acc"] * 2
    score -= trip["harsh_brake"] * 3

    if trip["max_speed"] > 100:
        score -= 10

    if score < 0:
        score = 0

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    else:
        grade = "D"
    # ----------------------------------

    result = {
        "trip_id": trip["trip_id"],
        "vehicle_uuid": vehicle_uuid,
        "start_time": trip["start_time"],
        "end_time": data["timestamp"],
        "trip_duration_sec": int(duration),
        "distance_km": round(distance, 3),
        "avg_speed": round(avg_speed, 2),
        "max_speed": trip["max_speed"],
        "harsh_brake_count": trip["harsh_brake"],
        "harsh_acceleration_count": trip["harsh_acc"],
        "driver_score": score,
        "grade": grade
    }

    if trip["start_fuel"] is not None:
        result["fuel_used"] = round(trip["start_fuel"] - data["fuel_level"], 2)

    if trip["start_soc"] is not None:
        result["battery_used"] = round(trip["start_soc"] - data["battery_soc"], 2)

    # publish trip
    trip_topic = f"fleet/{vehicle_uuid}/trip"
    client.publish(trip_topic, json.dumps(result))

    print("\n=========== TRIP SUMMARY ===========")
    print(result)
    print("====================================\n")

    # ---------- UPDATE LEADERBOARD ----------
    leaderboard[vehicle_uuid] = {
        "score": score,
        "grade": grade,
        "distance": round(distance, 2)
    }

    ranking = []

    sorted_board = sorted(
        leaderboard.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    for vid, info in sorted_board:
        ranking.append({
            "vehicle_uuid": vid,
            "score": info["score"],
            "grade": info["grade"]
        })

    leaderboard_payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "ranking": ranking
    }

    # publish leaderboard
    client.publish("fleet/leaderboard", json.dumps(leaderboard_payload))

    print("===== LEADERBOARD UPDATED =====")
    for i, item in enumerate(ranking, start=1):
        print(f"{i}. {item['vehicle_uuid'][:8]} → {item['score']} → {item['grade']}")
    print("================================\n")


# ---------------- MESSAGE HANDLER ----------------
def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())

    vehicle_uuid = data["uuid"]
    speed = data["speed"]

    # harsh detection
    prev = last_speed.get(vehicle_uuid, speed)
    delta = speed - prev
    last_speed[vehicle_uuid] = speed

    harsh_acc = 1 if delta > 15 else 0
    harsh_brake = 1 if delta < -15 else 0

    if vehicle_uuid not in trips:
        trips[vehicle_uuid] = {"active": False, "trip": None}

    state = trips[vehicle_uuid]

    # start
    if not state["active"] and speed > 0:
        state["trip"] = start_trip(data)
        state["active"] = True
        print("Trip started:", vehicle_uuid)

    # during
    if state["active"]:
        trip = state["trip"]
        trip["speed_sum"] += speed
        trip["speed_count"] += 1
        trip["max_speed"] = max(trip["max_speed"], speed)
        trip["harsh_brake"] += harsh_brake
        trip["harsh_acc"] += harsh_acc

    # end
    if state["active"] and speed == 0:
        end_trip(vehicle_uuid, state["trip"], data, client)
        state["active"] = False
        state["trip"] = None


# ---------------- MQTT ----------------
client = mqtt.Client()
client.connect(BROKER, PORT, 60)
client.subscribe("fleet/+/telemetry")
client.on_message = on_message

print("Trip engine running...")
client.loop_forever()
