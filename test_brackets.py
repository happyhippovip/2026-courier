with open("scripts/courier_real_worker_adapters.py", "r") as f:
    text = f.read()

def check(t):
    stack = []
    lines = t.split('\n')
    for i, line in enumerate(lines):
        for char in line:
            if char in "({[":
                stack.append((char, i+1))
            elif char in ")}]":
                if not stack:
                    return f"Extra {char} on line {i+1}"
                last = stack.pop()
                if (last[0] == '(' and char != ')') or \
                   (last[0] == '{' and char != '}') or \
                   (last[0] == '[' and char != ']'):
                    return f"Mismatched {char} on line {i+1} (opened {last[0]} on line {last[1]})"
    if stack:
        return f"Unclosed {stack[-1][0]} opened on line {stack[-1][1]}"
    return "OK"

print(check(text))
