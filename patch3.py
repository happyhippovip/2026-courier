def check_state(motor):
    resp = motor.get("/goals", headers={"Authorization": "Bearer test-secret"})
    print("GOALS:", resp.get_json())
