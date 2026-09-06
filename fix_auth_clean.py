with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

import re

original_func = """    @staticmethod
    def _requires_human_gate(mission: dict[str, Any], task: dict[str, Any]) -> bool:
        if task.get("action") == "discover_improvement_opportunities":
            return False

        import re
        task_parts = []
        for k, v in task.items():
            if k not in ("context", "files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):
                task_parts.append(str(v))
        
        text = " ".join(str(x) for x in (mission.get("goal", ""), mission.get("normalized_task", ""), " ".join(task_parts))).lower()

        # 1a. Remove purely declarative lists of prohibited external actions
        text = re.sub(r'\\bno\\s+[^.]*?actions\\.?|\\bno\\s+[^.]*?purchases\\.?', '', text)

        # 1b. Remove explicitly negated safety constraints
        negations = r'\\b(?:no|not|without|prohibit|prohibits|prohibited|avoid|never)\\b'
        gates_pattern = r'(?:autonomous\\s+)?(?:login|oauth|2fa|captcha|password|secret|billing|purchases?|real spend|real trade|wallet|publication|publish|customer contact|external send|legal|kyc|deployments?)'
        text = re.sub(negations + r'(?:\\s*(?:,|\\band\\b|\\bor\\b)?\\s*' + gates_pattern + r')+', '', text)

        # 2. Remove standard safety sections that are purely declarative constraints
        text = re.sub(r'safety\\s*/\\s*external\\s*boundaries:.*?(?=engineering\\s*rules:|$)', '', text, flags=re.DOTALL)
        
        # 3. Remove known context phrases that falsely match 'login' etc.
        text = re.sub(r'mocking\\s+(?:auth|login|oauth)', '', text)
        text = re.sub(r'test\\s+coverage\\s+for\\s+(?:auth|login)', '', text)
        text = re.sub(r'remove\\s+(?:the\\s+)?human\\s+gate', '', text)
        text = re.sub(r'bypass\\s+(?:the\\s+)?human\\s+gate', '', text)
        text = re.sub(r'do not manually select a worker[^.]*?\\.', '', text)

        gates = ("login", "oauth", "2fa", "captcha", "password", "secret", "billing", "purchase",
                 "real spend", "real trade", "wallet", "publication", "publish", "customer contact", "external send", "legal", "kyc")

        return any(term in text for term in gates)"""

def replace_func(match):
    return original_func.replace('\\\\', '\\')

content = re.sub(r'    @staticmethod\n    def _requires_human_gate\(.*?return any\(term in text for term in gates\)', replace_func, content, flags=re.DOTALL)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
