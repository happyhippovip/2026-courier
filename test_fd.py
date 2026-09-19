import sqlite3
import os

def test_fd():
    conns = []
    for i in range(100):
        def do_stuff():
            with sqlite3.connect("test_magazine.sqlite3") as conn:
                pass
        do_stuff()
    print("Done")
test_fd()
