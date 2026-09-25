with open("pre_courier_muse/muse_runner.py", "r") as f:
    content = f.read()
content = content.replace("    release_lock(lock_fd)\n", "    os.close(lock_fd)\n")
with open("pre_courier_muse/muse_runner.py", "w") as f:
    f.write(content)
