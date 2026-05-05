from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.dispute import ReturnData, DisputeAnalysis
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity, TaskStatus
from shopee_agent.persistence.repositories import ReturnDisputeRepository
from shopee_agent.providers.llm.gateway import LLMGateway
from shopee_agent.providers.shopee.gateway import ShopeeGateway
from shopee_agent.persistence.repositories import OrderRepository


class DisputeAgent:
    """Monitors, triages, and analyzes return/refund cases."""

    def __init__(
        self,
        shopee_gateway: ShopeeGateway,
        dispute_repo: ReturnDisputeRepository,
        supervisor: OperationsSupervisorAgent,
        llm: LLMGateway | None = None,
        vision: VisionAgent | None = None,
    ) -> None:
        self.shopee_gateway = shopee_gateway
        self.dispute_repo = dispute_repo
        self.supervisor = supervisor
        self.llm = llm
        self.vision = vision

    async def sync_returns(self, shop_id: str) -> int:
        """Sync returns from Shopee and trigger analysis for new cases."""
        return_list = await self.shopee_gateway.get_all_active_returns(shop_id)
        
        synced_count = 0
        for item in return_list:
            return_sn = item["return_sn"]
            # Get full detail for better analysis
            detail = await self.shopee_gateway.get_return_detail(shop_id, return_sn)
            
            # Shopee v2 returns 'due_date' (timestamp)
            due_ts = detail.get("due_date", 0)
            due_dt = datetime.fromtimestamp(due_ts) if due_ts else datetime.now() + timedelta(hours=48)
            
            data = ReturnData(
                return_sn=return_sn,
                order_sn=detail.get("order_sn", ""),
                shop_id=shop_id,
                buyer_id=str(detail.get("buyer_user_id", "")),
                reason=detail.get("reason", "UNKNOWN"),
                status=detail.get("status", "UNKNOWN"),
                amount=float(detail.get("refund_amount", 0.0)),
                text_reason=detail.get("text_reason", ""),
                evidence_urls=detail.get("image_urls", []),
                due_date=due_dt # New field
            )
            
            # Check if we already have this case and if it's already analyzed
            existing = self.dispute_repo.get_return(return_sn)
            self.dispute_repo.upsert_return(data)
            
            if not existing or existing.status != data.status:
                # Autonomous Evidence Gathering
                from shopee_agent.app.dispute_evidence_agent import DisputeEvidenceAgent
                from shopee_agent.persistence.repositories import ProductKnowledgeRepository
                order_repo = OrderRepository(self.dispute_repo.session)
                pk_repo = ProductKnowledgeRepository(self.dispute_repo.session)
                evidence_agent = DisputeEvidenceAgent(self.shopee_gateway, order_repo, pk_repo)
                evidence = await evidence_agent.collect_evidence(data.order_sn, shop_id)
                
                await self.analyze_case(data, evidence)
                synced_count += 1
                
        return synced_count

    async def analyze_case(self, data: ReturnData, evidence: dict | None = None) -> None:
        """Use LLM and evidence to analyze the dispute and raise an operator task."""
        evidence = evidence or {}
        risk_score = 0.5 # Default medium
        recommendation = "escalate"
        summary = "New dispute case received."
        vision_result = None
        
        # 1. Visual Analysis (Optional)
        if self.vision and data.evidence_urls:
            # Analyze the first buyer photo as a sample
            first_img = data.evidence_urls[0]
            vision_result = await self.vision.analyze_image(
                first_img, 
                prompt=(
                    f"Ini adalah foto bukti dari pembeli Shopee untuk pengembalian barang. "
                    f"Alasan pembeli: {data.reason}. "
                    f"Apakah foto ini menunjukkan kerusakan yang jelas? Jelaskan apa yang terlihat."
                )
            )
        
        # 2. Strategic Analysis
        if self.llm:
            context = {
                "reason": data.reason,
                "text_reason": data.text_reason,
                "amount": data.amount,
                "evidence_count": len(data.evidence_urls),
                "vision_analysis": vision_result
            }
            analysis_text = (
                f"Buyer Claim: {data.reason} - {data.text_reason}. "
                f"Vision Analysis: {vision_result or 'No images'}"
            )
            analysis = await self.llm.analyze_message(analysis_text, context)
            
            risk_score = analysis.urgency_score
            recommendation = "reject" if analysis.sentiment_score > 0 and not vision_result else "escalate"
            summary = analysis.reasoning or summary

        # Update repo with analysis
        self.dispute_repo.update_analysis(data.return_sn, recommendation, risk_score)
        
        # Create Operator Task
        # --- Revision: Hardened HITL scoring ---
        severity = TaskSeverity.P2
        if risk_score > 0.8: severity = TaskSeverity.P0
        elif risk_score > 0.5 or data.amount > 500000: severity = TaskSeverity.P1
        
        # God-Tier Escalation: P0 for proven physical mismatch or lack of evidence
        if evidence.get("weight_mismatch") or (len(data.evidence_urls) == 0 and data.amount > 100000):
            severity = TaskSeverity.P0
            summary += "\n🚨 **DETEKSI ANOMALI**: Berat fisik tidak sesuai atau bukti pembeli nihil."

        task = OperatorTask(
            task_id=f"dispute_{data.return_sn}",
            category="DISPUTE",
            subject_id=data.return_sn,
            shop_id=data.shop_id,
            severity=severity,
            title=f"🛡️ Dispute [{severity}]: {data.reason}",
            summary=(
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 **INFO PESANAN**\n"
                f"ID: `{data.order_sn}`\n"
                f"Total: `Rp {data.amount:,.0f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💬 **KLAIM PEMBELI**\n"
                f"_{data.text_reason or 'Tidak ada keterangan'}_\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👁️ **ANALISIS VISUAL (AI)**\n"
                f"{vision_result or 'Tidak ada foto bukti.'}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚖️ **ANALISIS BUKTI SISTEM**\n"
                f"• Status: `{evidence.get('logistics_status', 'N/A')}`\n"
                f"• Strategi: `{evidence.get('dispute_strategy', 'INVESTIGASI').replace('_', ' ')}`\n"
                f"• Berat: `{evidence.get('actual_weight', 0)}g` (Exp: `{evidence.get('expected_weight', 0)}g`)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 **KEPUTUSAN AGEN**\n"
                f"Tindakan: **{recommendation.upper().replace('ESCALATE', 'ESKALASI').replace('REJECT', 'TOLAK')}**\n"
                f"Risiko: `{risk_score:.2f}`\n"
                f"_{summary}_"
            ),
            status=TaskStatus.OPEN,
            due_at=data.due_date,
        )
        self.supervisor.create_task(task)
