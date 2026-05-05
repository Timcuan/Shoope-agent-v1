from __future__ import annotations

import re
from typing import TYPE_CHECKING
from shopee_agent.contracts.knowledge import ChatClassification, ChatDecision, ProductFact, ChatMessage, ChatAnalysis
from shopee_agent.contracts.domain import OrderData
from shopee_agent.providers.llm.gateway import LLMGateway

if TYPE_CHECKING:
    from shopee_agent.app.product_knowledge_agent import ProductKnowledgeAgent


class ChatAgent:
    """Classifies buyer messages and decides on automation actions."""

    INTENT_KEYWORDS = {
        "order_status": ["kapan", "sampai", "status", "dikirim", "resi", "lacak", "tracking", "belum datang", "mana"],
        "product_question": ["ready", "stok", "warna", "ukuran", "bahan", "ori", "asli", "pilih", "variasi"],
        "complaint": ["kecewa", "kurang", "salah", "rusak", "pecah", "cacat", "jelek", "komplain", "tidak sesuai"],
        "cancellation": ["batal", "cancel"],
        "refund": ["refund", "kembali dana", "balikin duit", "pengembalian dana"],
        "abuse": ["anjing", "babi", "bangsat", "goblok", "tolol", "penipu", "asu"],
        "general": ["halo", "min", "kak", "siang", "pagi", "sore", "malam", "terima kasih", "thanks"],
    }

    def __init__(self, llm: LLMGateway | None = None, pk_agent: ProductKnowledgeAgent | None = None) -> None:
        self.llm = llm
        self.pk_agent = pk_agent

    def classify(
        self, message: str, order_context: OrderData | None = None, product_facts: list[ProductFact] | None = None
    ) -> ChatClassification:
        """Deterministic intent classification based on keywords."""
        text = message.lower()
        matched_intents = []

        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(k in text for k in keywords):
                matched_intents.append(intent)

        # Priority if multiple match: abuse > refund > cancellation > complaint > product_question > order_status > general
        priority = ["abuse", "refund", "cancellation", "complaint", "product_question", "order_status", "general"]
        intent = "general"
        for p in priority:
            if p in matched_intents:
                intent = p
                break

        # Risk tiering
        risk_tier = "low"
        if intent in ["abuse", "refund"]:
            risk_tier = "high"
        elif intent in ["complaint", "cancellation"]:
            # If order value is high, escalate to high risk
            if order_context and order_context.total_amount > 500000:
                risk_tier = "high"
            else:
                risk_tier = "medium"
        elif intent == "product_question" and not product_facts:
            # If we don't have product info for a product question, it's medium risk
            risk_tier = "medium"

        return ChatClassification(
            intent=intent,
            risk_tier=risk_tier,
            confidence=0.9 if matched_intents else 0.5,
            reason_codes=matched_intents or ["no_keyword_match"],
        )

    async def decide(
        self, 
        message: str,
        classification: ChatClassification, 
        order_context: OrderData | None = None,
        product_facts: list[ProductFact] | None = None,
        history: list[ChatMessage] | None = None
    ) -> ChatDecision:
        """Decide action based on classification and LLM-assisted analysis."""
        action = "draft_for_approval"
        draft = None
        reasons = []
        analysis = None

        # LLM Assistance
        if self.llm:
            context = {
                "order": order_context.__dict__ if order_context else None,
                "product_facts": [p.__dict__ if hasattr(p, "__dict__") else p for p in (product_facts or [])]
            }
            analysis = await self.llm.analyze_message(message, context)

            # Build product knowledge context for AI
            product_context: str | None = None
            if self.pk_agent and product_facts:
                product_context = "\n\n".join(
                    self.pk_agent.build_context_for_ai(pf) for pf in product_facts
                )
            elif self.pk_agent and classification.intent == "product_question":
                # Try to auto-lookup product from message keywords
                if order_context and order_context.shop_id:
                    fact = self.pk_agent.lookup(order_context.shop_id, message)
                    if fact:
                        product_context = self.pk_agent.build_context_for_ai(fact)
            
            # --- Regional Expansion: Translation ---
            from shopee_agent.app.translation_agent import TranslationAgent
            translator = TranslationAgent(self.llm)
            lang = await translator.detect_language(message)
            
            if lang.lower() not in ["indonesian", "indonesia"]:
                reasons.append(f"translated_from_{lang.lower()}")
                # Draft in buyer's language
                system_suffix = f"\n\n[PENTING]: Gunakan bahasa {lang} untuk membalas pembeli ini."
            else:
                system_suffix = ""

            # Risk refinement based on sentiment/urgency
            if analysis.sentiment_score < -0.7 or analysis.urgency_score > 0.8:
                if classification.risk_tier == "low":
                    classification.risk_tier = "medium"
                    reasons.append("llm_detected_high_urgency_or_negativity")
                elif classification.risk_tier == "medium":
                    classification.risk_tier = "high"
                    reasons.append("llm_escalated_to_high_risk")
            
            # Generate draft
            draft = await self.llm.draft_response(
                classification, analysis, context, history, 
                product_context=product_context,
                system_prompt_suffix=system_suffix
            )
            
            if lang.lower() not in ["indonesian", "indonesia"]:
                # Provide Indo translation for the agent/admin
                indo_ver = await translator.translate(message, "Indonesian")
                draft = f"🌏 **Translated from {lang}**\n_Buyer:_ \"{indo_ver}\"\n\n{draft}"
            
            reasons.append("llm_generated_draft")
        else:
            draft = self._generate_draft(classification, order_context)
            reasons.append("template_generated_draft")

        if classification.intent == "abuse":
            action = "freeze"
            draft = "Otomasi dihentikan karena terdeteksi kata-kata kasar. Menunggu penanganan manual."
            reasons.append("abusive_language")
        
        # --- Shopee Policy Enforcement (Anti-PII & Anti-Off-Platform) ---
        # 1. Regex for phone numbers (ID standard)
        phone_pattern = r"(0|62|\+62)[\s\-]?8[1-9][0-9]{6,10}"
        if draft and re.search(phone_pattern, draft):
            action = "escalate"
            reasons.append("policy_violation_pii_detected")
            draft = f"⚠️ [BLOCKED] Draft mengandung nomor telepon.\n\n{draft}"
            
        # 2. Keywords for off-platform transactions
        forbidden_keywords = ["wa.me", "whatsapp", "transfer bank", "rekening", "no rek", "manual", "diluar shopee"]
        if draft and any(k in draft.lower() for k in forbidden_keywords):
            action = "escalate"
            reasons.append("policy_violation_off_platform")
            draft = f"⚠️ [BLOCKED] Draft terdeteksi transaksi luar platform.\n\n{draft}"

        # Decision Logic
        if action not in ["escalate", "freeze"]:
            if classification.risk_tier == "high":
                action = "escalate"
                reasons.append("high_risk_tier")
            elif classification.risk_tier == "medium":
                action = "draft_for_approval"
                reasons.append("medium_risk_needs_review")
            else:
                action = "auto_reply"
                reasons.append("low_risk_auto_reply")

        return ChatDecision(
            action=action,
            draft_reply=draft,
            reason_codes=reasons,
            classification=classification,
        )

    async def extract_knowledge_gap(self, history: list[ChatMessage], product_facts: list[ProductFact] | None = None) -> dict | None:
        """Analyze chat history to identify questions not covered by the current knowledge base."""
        if not self.llm or not history:
            return None
            
        chat_text = "\n".join([f"{'Buyer' if m.is_buyer else 'Agent'}: {m.content}" for m in history])
        kb_text = ""
        if product_facts:
            kb_text = "\n".join([str(p.faq_json) for p in product_facts])
            
        prompt = (
            f"Review this conversation between a Buyer and an AI Agent:\n\n{chat_text}\n\n"
            f"Current Knowledge Base for this product:\n{kb_text}\n\n"
            "Did the buyer ask a legitimate question that was NOT answered or was answered vaguely because it's missing from the Knowledge Base? "
            "If yes, formulate a new FAQ entry (Question and Answer). "
            "Reply in JSON format: {\"has_gap\": true, \"question\": \"...\", \"answer\": \"...\", \"reason\": \"...\"}. "
            "If no gap found, reply: {\"has_gap\": false}."
        )
        
        try:
            import json
            res_text = await self.llm.generate_response(prompt)
            # Find JSON in response
            match = re.search(r"\{.*\}", res_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if data.get("has_gap"):
                    return data
        except Exception:
            return None
        return None

    def _generate_draft(self, classification: ChatClassification, order_context: OrderData | None = None) -> str:
        """Simple template-based draft generation."""
        if classification.intent == "general":
            return "Halo Kak! Ada yang bisa kami bantu? 😊"
        
        if classification.intent == "order_status":
            if order_context:
                status_map = {
                    "READY_TO_SHIP": "sedang kami siapkan buat dikirim ya Kak",
                    "PROCESSED": "sudah diproses nih Kak, tinggal tunggu kurir pickup aja",
                    "SHIPPED": "sudah dalam perjalanan ke tempat Kakak ya",
                    "CANCELLED": "sayangnya sudah dibatalkan Kak",
                }
                status_desc = status_map.get(order_context.status, "sedang kami cek sebentar ya")
                return f"Halo Kak! Pesanan {order_context.order_sn} {status_desc}. Mohon ditunggu ya Kak! 🙏😊"
            return "Halo Kak! Boleh kami minta nomor pesanannya? Biar kami bantu cek status terbarunya ya! 😊"

        if classification.intent == "product_question":
            return "Halo Kak! Produknya ready ya, bisa langsung diorder biar segera kami proses pengirimannya. Ditunggu orderannya Kak! ✨😊"

        if classification.intent == "complaint":
            return "Aduh, maaf banget ya Kak atas ketidaknyamanannya. 🙏 Boleh infokan detail kendalanya atau kirim foto/video unboxingnya? Biar kami cariin solusi terbaik buat Kakak secepatnya ya! 🙏"

        return "Halo Kak! Pesannya sudah kami terima ya. Mohon tunggu sebentar, kami lagi cek dulu dan segera balik lagi buat bantu Kakak. 😊"
