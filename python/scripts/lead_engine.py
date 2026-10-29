
#!/usr/bin/env python3
"""MarketMinder AI - Lead Generation Engine"""
import json
import urllib.request
import time
from datetime import datetime

def get_auth_token():
    try:
        with open('/root/.hermes/auth.json') as f:
            data = json.load(f)
            return data['providers']['nous']['access_token']
    except:
        return None

def call_llm(prompt):
    token = get_auth_token()
    if not token:
        return None
    
    data = json.dumps({
        "model": "poolside/laguna-xs-2.1:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 300
    }).encode('utf-8')
    
    req = urllib.request.Request(
        "https://inference-api.nousresearch.com/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result["choices"][0]["message"]["content"]

# Target ICP (Ideal Customer Profile)
icp = {
    "title": ["Founder", "CEO", "Co-founder", "VP Marketing"],
    "company_size": ["10-50 employees", "1-10 employees"],
    "industry": ["SaaS", "Technology", "E-commerce", "Fintech"],
    "pain_points": [
        "manual competitor research",
        "scattered market intelligence",
        "time-consuming analysis",
        "expensive enterprise tools"
    ]
}

print("=== MarketMinder AI - Lead Generation Engine ===")
print(f"Started at: {datetime.now()}")
print()

# Generate personalized outreach for different ICPs
for title in icp["title"][:2]:
    for industry in icp["industry"][:2]:
        print(f"Generating outreach for: {title} at {industry} company")
        prompt = f"""
Write a cold email for a {title} at a {industry} company about MarketMinder AI.
The email should:
1. Reference their specific role and industry
2. Mention a pain point (manual competitor research, scattered intelligence)
3. Offer a specific value proposition
4. Include a soft CTA for a demo
5. Be under 100 words

Format: Subject line + email body
        """
        email = call_llm(prompt)
        if email:
            print(f"  Subject: {email.split(chr(10))[0][:60]}...")
            print(f"  Body length: {len(email)} chars")
        time.sleep(2)

print()
print("Lead generation complete!")
print("Next: Send emails, track responses, schedule demos")
