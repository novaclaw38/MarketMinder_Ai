
#!/usr/bin/env python3
"""MarketMinder AI - Automated Content Distribution"""
import json
import urllib.request
import time
import random
from datetime import datetime

# Content topics for SEO
topics = [
    "competitive intelligence for small businesses",
    "market research automation tools",
    "how to analyze competitors",
    "competitive analysis template",
    "market trends in AI startups",
    "business intelligence for startups",
    "competitor monitoring tools",
    "market research for SaaS",
    "competitive landscape analysis",
    "AI market research"
]

# Subreddits to post to
subreddits = [
    "startups",
    "entrepreneur", 
    "smallbusiness",
    "SaaS",
    "marketing"
]

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
        "max_tokens": 500
    }).encode('utf-8')
    
    req = urllib.request.Request(
        "https://inference-api.nousresearch.com/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result["choices"][0]["message"]["content"]

print("=== MarketMinder AI - Content Distribution Engine ===")
print(f"Started at: {datetime.now()}")
print()

# Generate content for each topic
for topic in topics[:3]:
    print(f"Generating content for: {topic}")
    prompt = f"Write a 200-word blog post about {topic}. Include a compelling title and call to action for MarketMinder AI."
    content = call_llm(prompt)
    if content:
        print(f"  Title: {content.split(chr(10))[0][:80]}")
        print(f"  Content length: {len(content)} chars")
        # In production, this would post to Reddit, IndieHackers, etc.
        time.sleep(2)
    else:
        print("  Failed to generate content")

print()
print("Content generation complete!")
print("Next: Post to communities, send cold emails, launch ads")
