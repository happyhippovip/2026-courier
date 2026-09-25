with open('scripts/headless_night.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_start = '''                started = motor.start(
                    cooldown=motor.m.get('cooldown_seconds', COOLDOWN_SECONDS),
                    local_fake=motor.m.get('local_fake', False),
                    continuous_canary=motor.m.get('continuous_canary', False))'''

old_start = '''                started = motor.start(
                    cooldown=motor.m.get('cooldown_seconds', COOLDOWN_SECONDS),
                    local_fake=motor.m.get('local_fake', False))'''

if new_start in content:
    content = content.replace(new_start, old_start)
    with open('scripts/headless_night.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Reverted headless_night.py!")
