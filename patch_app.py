import sys

def patch():
    with open('server/app.py', 'r') as f:
        content = f.read()

    content = content.replace(
        'STATE_LOCK = CrossProcessFileLock(f"{STATE_FILE}.lock")',
        '# STATE_LOCK removed for thread safety'
    )
    content = content.replace(
        'with STATE_LOCK:',
        'with CrossProcessFileLock(f"{STATE_FILE}.lock"):'
    )

    with open('server/app.py', 'w') as f:
        f.write(content)
    print("Patched app.py successfully")

if __name__ == '__main__':
    patch()
