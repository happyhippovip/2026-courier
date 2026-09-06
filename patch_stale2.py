with open("scripts/courier_founder_mode.py", "r") as f:
    text = f.read()

# I need to modify `_pop(data)` so that if it modifies `g["status"] = "PENDING"`, it returns a tuple or something?
# No, `_mutate` saves `data` whenever it returns. But wait!
# If it returns `g` (which it does when it finds PENDING), it WILL save!
# Let's check `test_pop.py` again. Did it save?
