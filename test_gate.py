from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
import json
import re

with open('events/mission-queue/queue.json') as f:
    q = json.load(f)

for m in q['missions']:
    if m['status'] == 'HUMAN_GATE':
        task = m['task']
        mission = m
        task_parts = []
        for k, v in task.items():
            if k not in ("files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):
                task_parts.append(str(v))
        
        raw_text = " ".join(str(x) for x in (mission.get("goal", ""), mission.get("normalized_task", ""), " ".join(task_parts)))
        text = raw_text.lower()
        print('TEXT BEFORE STRIP:', repr(text))
        
        text = re.sub(r'safety\s*/\s*external\s*boundaries:.*?(?=engineering\s*rules:|$)', '', text, flags=re.DOTALL)
        text = re.sub(r'\bhuman_gate\s+(?:remains?\s+)?required\s+for:.*?(?=engineering\s*rules:|$)', '', text, flags=re.DOTALL)
        text = re.sub(r'[^.]*?\bremains?\s+human_gate\b[^.]*?\.', '', text)
        text = re.sub(r'[^.]*?\bstop\s+at\s+human_gate\b[^.]*?\.', '', text)
        text = re.sub(r'do not manually select a worker[^.]*?\.', '', text)
        text = re.sub(r'\bwithout\s+[^.;\n]+?(?=[.;\n]|\b(?:but|while|instead)\b|$)', '', text)
        text = re.sub(r'\b(?:do\s+not|don\'t|dont|does\s+not|doesn\'t|doesnt|did\s+not|didn\'t|didnt|must\s+not|cannot|can\'t|cant|should\s+not|shouldn\'t|never|avoid|prohibit|prohibits|prohibited|not\s+requir\w*)\s+[^.;\n]+?(?=[.;\n]|\b(?:but|while|instead)\b|$)', '', text)
        text = re.sub(r'\bno\s+(?:deployment|deployments|publication|publish|purchases?|spending|spend|customer\s+contact|external\s+(?:sends?|services?)|wallet(?:\s+\w+)?|real\s+trades?|real-money(?:\s+\w+)?|oauth|login|2fa|captcha|credentials|human\s+approval|human\s+gate|account\s+automation|upgrades?|overages?)\b[^.;\n]*', '', text)
        text = re.sub(r'\bspend\s*[:=]\s*0\b|\b0\s*eur\s*spend\b|\b0\s*spend\b', '', text)
        
        print('TEXT AFTER STRIP:', repr(text))
        gated_action_patterns = [
            r'\b(?:deploy|deploying|deployment)\b',
            r'\b(?:publish|publishing|publication)\b',
            r'\b(?:contact|contacting|email|message|reach\s+out\s+to)\s+(?:customers?|users?|clients?)\b',
            r'\b(?:send|sending)\s+(?:external|emails?|sms|messages?)\s+to\b',
            r'\b(?:login|log\s+in|logging\s+in|authenticate|authenticating)\b',
            r'\b(?:oauth|2fa|two-factor|two\s+factor|captcha|password|secret\s+key)\b',
            r'\b(?:purchase|purchasing|buy|buying|pay|paying|billing)\b',
            r'\b(?:real\s+spend|real\s+money|real\s+trades?|trading|trade\s+execution)\b',
            r'\b(?:wallet\s+signing|sign\s+transaction|sign\s+wallet)\b',
            r'\b(?:human\s+approval\s+required|human\s+gate\s+required)\b',
            r'\b(?:kyc|legal\s+contract)\b',
        ]
        
        fallback_keywords = (
            "deploy", "deployment", "login", "oauth", "2fa", "captcha", "password", "secret", "billing", "purchase", "authenticate", "human approval",
            "real spend", "real trade", "wallet", "publication", "publish", "customer contact", "external send", "legal", "kyc"
        )
        
        for pat in gated_action_patterns:
            if re.search(pat, text):
                print('MATCHED PATTERN:', pat)
        
        for term in fallback_keywords:
            if term in text:
                print('MATCHED FALLBACK:', term)
