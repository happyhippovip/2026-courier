import hashlib

def test(s, target):
    if hashlib.sha256(s.encode('utf-8')).hexdigest() == target:
        print("MATCH:", s)

test("REQ-MAC-7405254D" + "PASS" + "Bounded validation for WINDOWS_COMPATIBILITY completed autonomously via WINDOWS_GOOGLE", "ad13f98269ba49f3d83128a9208dc9a1d88f39904ecb789e961b0db1d03170e4")
