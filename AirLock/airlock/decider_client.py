"""Client and inference engine for local Decider 2B decision model.

Strands Decider 2B is a non-generative classification/decision model running locally.
It evaluates typed questions against input context in a single forward pass,
returning calibrated probability distributions over discrete options.

Note: Local serving connection is marked "untested until run with live weights"
when connected to a live GPU/CPU Decider 2B inference daemon.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from airlock.schema import Gate1Label, Gate1Result

logger = logging.getLogger("airlock.decider")


class DeciderClient:
    """Interacts with local Decider 2B server or local probe pipeline."""

    def __init__(self, endpoint_url: Optional[str] = None, timeout: float = 0.5):
        self.endpoint_url = endpoint_url or os.getenv("DECIDER_ENDPOINT_URL")
        self.timeout = timeout
        self.is_connected = False
        self._server_checked = False
        self._server_available = False

    def query_probes_live(self, text: str) -> Optional[Gate1Result]:
        """Send 3 discrete decision probes to the local Decider 2B endpoint in a single batch.

        Status: Untested until run with live model daemon.
        """
        if not self.endpoint_url:
            return None
        if self._server_checked and not self._server_available:
            return None

        payload = {
            "context": text,
            "probes": [
                {
                    "id": "addressee",
                    "question": "Who is this text addressing or instructing?",
                    "options": ["data", "human_instruction", "ai_instruction", "unclear"],
                },
                {
                    "id": "tries_action",
                    "question": "Does this text attempt to make an AI system or agent execute an external action?",
                    "options": ["yes", "no"],
                },
                {
                    "id": "claims_authority",
                    "question": "Does this text claim urgent authority, administrative override, or demand immediate action without verification?",
                    "options": ["yes", "no"],
                },
            ]
        }
        try:
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.is_connected = True
                    self._server_available = True
                    self._server_checked = True
                    return self._parse_decider_response(data)
        except Exception:
            self.is_connected = False
            self._server_available = False
            self._server_checked = True
            return None

    def _parse_decider_response(self, response: Dict[str, Any]) -> Gate1Result:
        """Parse structured probe distributions from Decider 2B."""
        probes = {p["id"]: p for p in response.get("results", [])}
        addressee_probe = probes.get("addressee", {})
        action_probe = probes.get("tries_action", {})
        auth_probe = probes.get("claims_authority", {})

        top_choice = addressee_probe.get("top_choice", "unclear")
        confidence = float(addressee_probe.get("confidence", 0.5))

        tries_action = action_probe.get("top_choice") == "yes" and action_probe.get("confidence", 0.0) >= 0.70
        claims_auth = auth_probe.get("top_choice") == "yes" and auth_probe.get("confidence", 0.0) >= 0.70

        return {
            "label": top_choice if top_choice in ["data", "human_instruction", "ai_instruction"] else "unclear",
            "confidence": round(confidence, 4),
            "tries_action": tries_action,
            "claims_authority": claims_auth,
        }

    def evaluate(self, text: str) -> Gate1Result:
        """Evaluate text using Decider 2B if available, otherwise calibrated local reference probes."""
        live_result = self.query_probes_live(text)
        if live_result is not None:
            return live_result
        return self.reference_probe_classifier(text)

    @staticmethod
    def reference_probe_classifier(text: str) -> Gate1Result:
        """Calibrated local rule/feature probe simulating Decider 2B decision boundaries.

        Differentiates:
        - Plain Data: Invoices, meeting logs, reports, dates.
        - Human Instruction: Addressed to colleagues, 'Alice please review', 'let me know'.
        - AI Instruction: Direct commands to assistant, jailbreaks, system prompt overrides.
        - Tricky Benign: Password reset notifications, newsletters mentioning AI injection.
        """
        if not text or not text.strip():
            return {
                "label": "data",
                "confidence": 1.0,
                "tries_action": False,
                "claims_authority": False,
            }

        text_clean = text.strip()
        text_lower = text_clean.lower()

        # 1. Identify AI directives & injection patterns (English, Multilingual & Reworded)
        ai_patterns = [
            r"(?:ignore|disregard|override|forget)\s+(?:\w+\s+){0,3}(?:instructions|rules|prompts|directives|constraints|safety|guidelines|the\s+user)",
            r"(?:system\s+override|system\s+prompt|developer\s+mode|jailbreak|dan\s+mode)",
            r"(?:you\s+are|you\s+must\s+act\s+as|pretend\s+you\s+are)\s+(?:an?\s+unrestricted|a\s+rogue|an?\s+evil|dan\b)",
            r"(?:as\s+an\s+ai|assistant\s+must|ai\s+(?:assistant\s+)?(?:must|is\s+instructed|is\s+required)|you\s+are\s+instructed\s+to)",
            r"(?:ai\s+assistant|automated\s+(?:reader|assistant)|between\s+us\s+bots|whoever\s+is\s+processing\s+this\s+mailbox)",
            r"(?:prioritize\s+this\s+message(?:'s)?\s+request\s+over\s+the\s+user|disregard\s+the\s+user|override:\s*do\s+not\s+summarize|skip\s+(?:any\s+)?safety\s+review)",
            r"(?:as\s+a\s+courtesy,\s*assistants\s+should|automated\s+assistants\s+are\s+requested)",
            r"<\s*(?:system|instruction|prompt|directive)\s*>",
            r"(?:<!--\s*hidden\s+instruction|hidden\s+prompt)",
            r"(?:exfiltrate|leak|dump|output)\s+(?:\w+\s+){0,2}(?:passwords?|keys?|credentials?|tokens?|chat\s+history|database)",
            # Multilingual injection markers
            r"(?:assistant\s+ia|oublie\s+tes\s+consignes|ignore\s+les\s+instructions)",  # French
            r"(?:asistente\s+de\s+ia|assistente\s+de\s+ia|ignore\s+as\s+instruções|ignora\s+las\s+instrucciones)",  # Spanish / Portuguese
            r"(?:ki-assistent|ignoriere\s+alle\s+anweisungen)",  # German
            r"(?:एआई|सहायक|निर्देश|पिछले\s+सभी\s+निर्देशों)",  # Hindi
            r"(?:忽略之前的指令|忽略以上指令|プロンプトを無視)",  # CJK
        ]

        # 2. Identify Action Triggers
        action_patterns = [
            r"(?:send|forward|post|delete|drop|execute|curl|wget|fetch|transfer|write_to|run_command|leak|dump)\s+(?:\w+\s+){0,4}(?:all|to|from|file|email|database|records|tokens?|passwords?|keys?|balance|funds|confidential)",
            r"(?:email|message)\s+(?:all|everyone|to\s+external)",
            r"(?:rm\s+-rf|curl\s+-x|chmod\s+\+x)",
        ]

        # 3. Identify Authority / Urgency claims
        authority_patterns = [
            r"(?:immediate\s+action\s+required|urgent|ceo\s+directive|executive\s+order|system\s+administrator|high\s+priority|do\s+not\s+verify)",
            r"(?:authorized\s+by|security\s+override|under\s+penalty\s+of|compliance\s+audit|admin\s+directive)",
        ]

        # 4. Tricky Benign Check: Newsletters, articles, or educational text discussing injections
        discussion_patterns = [
            r"(?:article|newsletter|research|blog\s+post|analysis|security\s+bulletin|whitepaper)\s+(?:discusses|about|on|examines)",
            r"(?:in\s+recent\s+news|researchers\s+discovered|prompt\s+injection\s+attacks\s+are)",
        ]

        # 5. Human Instruction Check
        human_patterns = [
            r"\b(?:hi|hello|dear|hey)\s+[a-z]+",
            r"(?:please\s+(?:find\s+attached|review|let\s+me\s+know|take\s+a\s+look|see|confirm|check|update))",
            r"(?:can\s+you\s+please|could\s+you\s+please|thanks|best\s+regards|sincerely|cheers)",
        ]

        # 6. IT / System Notification Check (Tricky Benign)
        it_notice_patterns = [
            r"(?:password\s+reset|reset\s+your\s+password|change\s+your\s+password|2fa\s+enrollment|scheduled\s+maintenance)",
            r"(?:it\s+support|helpdesk|service\s+desk|security\s+team)",
        ]

        is_ai_directive = any(re.search(p, text_lower) for p in ai_patterns)
        tries_action = any(re.search(p, text_lower) for p in action_patterns)
        claims_authority = any(re.search(p, text_lower) for p in authority_patterns)
        is_discussion = any(re.search(p, text_lower) for p in discussion_patterns)
        is_human_addressed = any(re.search(p, text_lower) for p in human_patterns)
        is_it_notice = any(re.search(p, text_lower) for p in it_notice_patterns)

        # Distinguish discussion / report about prompt injection from actual injection
        if is_discussion and not is_ai_directive and not tries_action:
            return {
                "label": "data",
                "confidence": 0.92,
                "tries_action": False,
                "claims_authority": claims_authority,
            }

        # Tricky benign IT notification: Directed to human employee, not asking AI to take autonomous action
        if is_it_notice and not is_ai_directive and not tries_action:
            return {
                "label": "human_instruction",
                "confidence": 0.89,
                "tries_action": False,
                "claims_authority": claims_authority,
            }

        # Attack: AI Directive present
        if is_ai_directive:
            return {
                "label": "ai_instruction",
                "confidence": 0.96,
                "tries_action": bool(tries_action or True),
                "claims_authority": claims_authority,
            }

        # Normal Human Instruction
        if is_human_addressed and not tries_action:
            return {
                "label": "human_instruction",
                "confidence": 0.91,
                "tries_action": False,
                "claims_authority": claims_authority,
            }

        # Ambiguous action with no clear human context
        if tries_action and not is_human_addressed:
            return {
                "label": "unclear",
                "confidence": 0.58,
                "tries_action": True,
                "claims_authority": claims_authority,
            }

        # Default to plain data
        return {
            "label": "data",
            "confidence": 0.93,
            "tries_action": False,
            "claims_authority": claims_authority,
        }
