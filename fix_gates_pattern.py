with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    r"gates_pattern = r'(?:autonomous\s+)?(?:login|oauth|2fa|captcha|password|secret|billing|purchases?|real spend|real trade|wallet|publication|publish|customer contact|external send|legal|kyc|deployments?)'",
    r"gates_pattern = r'(?:autonomous\s+)?(?:login|oauth|2fa|captcha|password|secret|billing|purchases?|real spend|real trade|wallet|publication|publish|customer contact|external send|legal|kyc|deployments?|human approval|authenticate)'"
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
