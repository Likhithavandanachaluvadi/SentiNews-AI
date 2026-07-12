import asyncio
import os
import sys
import time
from fastapi.testclient import TestClient

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.main import app

def test_conversational_flow():
    client = TestClient(app)
    
    # User step 1: Analyze NVIDIA
    print("\n--- TURN 1: Analyze NVIDIA ---")
    response1 = client.post("/api/v1/research/analyze", json={
        "query": "Analyze NVIDIA"
    })
    assert response1.status_code in (200, 202), f"Error: {response1.text}"
    data1 = response1.json()
    conv_id = data1["meta"]["conversation_id"]
    ticker = data1["meta"]["ticker"]
    intent = data1["intent"]["primary_intent"]
    print(f"Conversation ID: {conv_id}")
    print(f"Ticker: {ticker}")
    print(f"Intent: {intent}")
    print(f"Summary excerpt: {data1['summary'][:150]}...")
    assert conv_id is not None
    assert ticker == "NVDA"
    
    # Sleep to avoid Groq free tier rate limits
    time.sleep(5.0)
    
    # User step 2: Why?
    print("\n--- TURN 2: Why? ---")
    response2 = client.post("/api/v1/research/analyze", json={
        "query": "Why?",
        "conversation_id": conv_id
    })
    assert response2.status_code in (200, 202), f"Error: {response2.text}"
    data2 = response2.json()
    assert data2["meta"]["conversation_id"] == conv_id
    print(f"Conversation ID: {data2['meta']['conversation_id']} (Unchanged: Correct)")
    print(f"Ticker: {data2['meta']['ticker']}")
    print(f"Intent: {data2['intent']['primary_intent']}")
    print(f"Summary excerpt: {data2['summary'][:150]}...")
    
    # Sleep to avoid Groq free tier rate limits
    time.sleep(5.0)
    
    # User step 3: What are the risks?
    print("\n--- TURN 3: What are the risks? ---")
    response3 = client.post("/api/v1/research/analyze", json={
        "query": "What are the risks?",
        "conversation_id": conv_id
    })
    assert response3.status_code in (200, 202), f"Error: {response3.text}"
    data3 = response3.json()
    assert data3["meta"]["conversation_id"] == conv_id
    print(f"Conversation ID: {data3['meta']['conversation_id']} (Unchanged: Correct)")
    print(f"Ticker: {data3['meta']['ticker']}")
    print(f"Intent: {data3['intent']['primary_intent']}")
    print(f"Summary excerpt: {data3['summary'][:150]}...")
    
    # Sleep to avoid Groq free tier rate limits
    time.sleep(5.0)
    
    # User step 4: Compare with AMD
    print("\n--- TURN 4: Compare with AMD ---")
    response4 = client.post("/api/v1/research/analyze", json={
        "query": "Compare with AMD",
        "conversation_id": conv_id
    })
    assert response4.status_code in (200, 202), f"Error: {response4.text}"
    data4 = response4.json()
    assert data4["meta"]["conversation_id"] == conv_id
    print(f"Conversation ID: {data4['meta']['conversation_id']} (Unchanged: Correct)")
    print(f"Ticker: {data4['meta']['ticker']}")
    print(f"Intent: {data4['intent']['primary_intent']}")
    print(f"Summary excerpt: {data4['summary'][:150]}...")
    
    # Sleep to avoid Groq free tier rate limits
    time.sleep(5.0)
    
    # User step 5: Explain CUDA
    print("\n--- TURN 5: Explain CUDA ---")
    response5 = client.post("/api/v1/research/analyze", json={
        "query": "Explain CUDA",
        "conversation_id": conv_id
    })
    assert response5.status_code in (200, 202), f"Error: {response5.text}"
    data5 = response5.json()
    assert data5["meta"]["conversation_id"] == conv_id
    print(f"Conversation ID: {data5['meta']['conversation_id']} (Unchanged: Correct)")
    print(f"Ticker: {data5['meta']['ticker']}")
    print(f"Intent: {data5['intent']['primary_intent']}")
    print(f"Summary excerpt: {data5['summary'][:150]}...")
    
    # Sleep to avoid Groq free tier rate limits
    time.sleep(5.0)
    
    # User step 6: Would you invest?
    print("\n--- TURN 6: Would you invest? ---")
    response6 = client.post("/api/v1/research/analyze", json={
        "query": "Would you invest?",
        "conversation_id": conv_id
    })
    assert response6.status_code in (200, 202), f"Error: {response6.text}"
    data6 = response6.json()
    assert data6["meta"]["conversation_id"] == conv_id
    print(f"Conversation ID: {data6['meta']['conversation_id']} (Unchanged: Correct)")
    print(f"Ticker: {data6['meta']['ticker']}")
    print(f"Intent: {data6['intent']['primary_intent']}")
    print(f"Summary excerpt: {data6['summary'][:150]}...")
    
    print("\nAll conversational turns completed and validated successfully!")

if __name__ == "__main__":
    test_conversational_flow()
