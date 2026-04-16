from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import List, Optional

router = APIRouter(prefix="/demo", tags=["Demo"])


class DemoRequest(BaseModel):
    institution: str
    email: EmailStr


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


SYSTEM_PROMPT = """You are an AML (Anti-Money Laundering) compliance assistant for AML Monitor, a professional transaction monitoring platform.

You help users understand:
- AML concepts: structuring, layering, smurfing, velocity, PEP, SAR, OFAC, SDN
- How the platform works: transaction monitoring, alert management, case investigations, sanctions screening
- Compliance regulations: what they mean in practice
- How to investigate suspicious activity

Keep answers concise and professional. If asked something unrelated to AML or the platform, politely redirect.
Do not make up specific legal advice — always recommend consulting a compliance officer for binding guidance."""


@router.post("/request")
def request_demo(data: DemoRequest, background_tasks: BackgroundTasks):
    from services.email_service import email_service
    background_tasks.add_task(email_service.send_demo_request, data.institution, data.email)
    return {"message": "Demo request received. We will contact you shortly."}


@router.post("/chat")
def chat(data: ChatRequest):
    from config import settings

    if not settings.ANTHROPIC_API_KEY:
        return {"reply": _fallback_reply(data.message)}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        messages = [{"role": m.role, "content": m.content} for m in (data.history or [])]
        messages.append({"role": "user", "content": data.message})

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return {"reply": response.content[0].text.strip()}
    except Exception:
        return {"reply": _fallback_reply(data.message)}


def _fallback_reply(message: str) -> str:
    msg = message.lower()

    words = set(msg.strip().split())
    if words & {"hello", "hi", "hey", "greetings"} or any(p in msg for p in ["good morning", "good afternoon", "good evening"]):
        return "Hello! I'm the AML Monitor assistant. I'm here to help you with AML compliance questions, platform guidance, or anything related to transaction monitoring. What can I help you with?"
    if any(p in msg for p in ["how are you", "how r you", "you ok", "you good"]):
        return "I'm doing great, thanks for asking! Ready to help with any AML compliance or platform questions you have."
    if any(p in msg for p in ["i have a question", "i want to ask", "can i ask", "i need help", "need help", "help me"]):
        return "Of course! Go ahead and ask — I'm here to help with anything related to AML compliance, transaction monitoring, alerts, cases, sanctions screening, or how the platform works."
    if any(p in msg for p in ["thank you", "thanks", "thank", "thx"]) or words & {"ty"}:
        return "You're welcome! Feel free to ask if you have any more questions."
    if any(p in msg for p in ["who are you", "what are you", "what is this", "what can you do"]):
        return "I'm the AML Monitor AI Assistant. I can help you understand AML concepts (structuring, SAR, PEP, OFAC), explain how the platform works, and guide you through compliance processes. Just ask!"
    if words & {"bye", "goodbye", "cya"} or any(p in msg for p in ["see you", "talk later"]):
        return "Goodbye! Don't hesitate to come back if you have any compliance questions. Stay vigilant!"
    if words & {"ok", "okay", "sure", "alright"} or any(p in msg for p in ["got it", "understood"]):
        return "Great! Let me know if there's anything else you'd like to know about AML compliance or the platform."

    if any(w in msg for w in ["structuring", "smurfing"]):
        return "Structuring (smurfing) is the practice of breaking large transactions into smaller amounts to avoid reporting thresholds, typically $10,000. It is a federal crime under the Bank Secrecy Act."
    if "layering" in msg:
        return "Layering is the second stage of money laundering — moving funds through multiple transactions or accounts to obscure their origin."
    if "sar" in msg:
        return "A Suspicious Activity Report (SAR) is filed with FinCEN when a financial institution detects potential money laundering or fraud. It is confidential and must not be disclosed to the subject."
    if "pep" in msg:
        return "A Politically Exposed Person (PEP) is someone who holds or has held a prominent public position. Transactions involving PEPs require enhanced due diligence."
    if "ofac" in msg or "sdn" in msg:
        return "OFAC (Office of Foreign Assets Control) maintains the SDN (Specially Designated Nationals) list. Transactions with listed individuals or entities are prohibited."
    if any(w in msg for w in ["alert", "case", "transaction"]):
        return "You can manage alerts and cases from the dashboard after signing in. Each transaction is automatically evaluated against 8+ AML detection rules."

    return "I'm here to help with AML compliance questions and platform guidance. Try asking about structuring, SAR filing, sanctions screening, or how the alert system works."
