from server.app import app
import json, time

def test_release():
    client = app.test_client()
    state = client.get("/state", headers={"Authorization": "Bearer x"}).get_json()
    print("State tasks:", len(state.get("tasks", {})))

test_release()
