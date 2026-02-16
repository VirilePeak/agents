import json
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class AdAnalysis:
    """Structured output from LLM analysis"""
    opportunity_type: str  # airdrop, listing, partnership, narrative, etc.
    confidence: int  # 1-10
    action_recommendation: str
    risk_level: str  # low, medium, high
    why_it_works: str  # One sentence, concrete


class AdAnalyzer:
    """
    Analyzes ad creative and explains why it works.
    
    Supports:
    - Local LLM (Ollama)
    - OpenAI API
    - Simple rule-based fallback
    """
    
    def __init__(self, mode: str = "local", model: str = "llama3.2:latest"):
        self.mode = mode
        self.model = model
        self.ollama_url = "http://localhost:11434/api/generate"
    
    def analyze(self, ad_data: Dict) -> AdAnalysis:
        """
        Analyze ad and generate 'Why it works' explanation.
        
        Args:
            ad_data: Dict with brand, headline, primary_text, cta, format
            
        Returns:
            AdAnalysis with structured insights
        """
        if self.mode == "local":
            return self._analyze_local(ad_data)
        elif self.mode == "openai":
            return self._analyze_openai(ad_data)
        else:
            return self._analyze_rules(ad_data)
    
    def _analyze_local(self, ad_data: Dict) -> AdAnalysis:
        """Use local Ollama LLM"""
        import requests
        
        prompt = self._build_prompt(ad_data)
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            
            result = response.json()
            output = json.loads(result.get("response", "{}"))
            
            return AdAnalysis(
                opportunity_type=output.get("type", "unknown"),
                confidence=output.get("confidence", 5),
                action_recommendation=output.get("action", "monitor"),
                risk_level=output.get("risk", "medium"),
                why_it_works=output.get("why", self._generate_why_fallback(ad_data))
            )
            
        except Exception as e:
            print(f"Local LLM error: {e}, falling back to rules")
            return self._analyze_rules(ad_data)
    
    def _analyze_openai(self, ad_data: Dict) -> AdAnalysis:
        """Use OpenAI API"""
        # Placeholder - implement if needed
        return self._analyze_rules(ad_data)
    
    def _analyze_rules(self, ad_data: Dict) -> AdAnalysis:
        """
        Rule-based analysis when LLM unavailable.
        Fast, deterministic, zero cost.
        """
        headline = ad_data.get("headline", "").lower()
        primary = ad_data.get("primary_text", "").lower()
        cta = ad_data.get("cta", "").lower()
        
        # Pattern detection
        patterns = []
        
        # UGC pattern
        if any(word in primary for word in ["i tried", "my experience", "honest review", "real results"]):
            patterns.append("Authentic UGC builds trust through personal storytelling")
        
        # Scarcity pattern
        if any(word in headline + primary for word in ["limited", "only", "left", "ends soon", "last chance"]):
            patterns.append("Scarcity urgency drives immediate action through FOMO")
        
        # Social proof pattern
        if any(word in primary for word in ["join", "customers", "people", "rated", "stars", "reviews"]):
            patterns.append("Social proof validates quality through community validation")
        
        # Discount pattern
        if any(word in headline for word in ["% off", "save", "free", "$", "deal", "sale"]):
            patterns.append("Clear value proposition removes price friction immediately")
        
        # Problem-solution pattern
        if any(word in primary for word in ["tired of", "struggle", "finally", "solution", "fix"]):
            patterns.append("Problem-agitation creates emotional buy-in before solution")
        
        # Authority pattern
        if any(word in primary for word in ["expert", "doctor", "study", "research", "proven", "clinical"]):
            patterns.append("Authority cues transfer credibility and reduce skepticism")
        
        # Curiosity gap pattern
        if "?" in headline or any(word in headline for word in ["secret", "trick", "hack", "revealed"]):
            patterns.append("Curiosity gap creates information hunger requiring click")
        
        # Default pattern
        if not patterns:
            patterns.append("Direct offer clarity reduces decision friction for ready buyers")
        
        # Select best pattern (first match or default)
        why = patterns[0] if patterns else "Clear messaging matches buyer intent at decision moment"
        
        # Determine type
        ad_type = "brand_awareness"
        if "sale" in headline or "%" in headline or "free" in headline:
            ad_type = "promotional"
        elif any(word in primary for word in ["learn", "how to", "guide", "tips"]):
            ad_type = "educational"
        elif any(word in cta for word in ["shop", "buy", "order"]):
            ad_type = "conversion"
        
        # Calculate confidence based on pattern strength
        confidence = min(5 + len(patterns) * 2, 10)
        
        # Risk assessment
        risk = "low"
        if any(word in primary for word in ["guarantee", "risk-free", "money back"]):
            risk = "low"
        elif ad_type == "promotional":
            risk = "medium"
        
        return AdAnalysis(
            opportunity_type=ad_type,
            confidence=confidence,
            action_recommendation="study_creative" if confidence >= 7 else "monitor",
            risk_level=risk,
            why_it_works=why
        )
    
    def _build_prompt(self, ad_data: Dict) -> str:
        """Build prompt for LLM"""
        return f"""Analyze this Facebook ad and explain why it works in ONE sentence.

Brand: {ad_data.get('brand', 'Unknown')}
Headline: {ad_data.get('headline', '')}
Primary Text: {ad_data.get('primary_text', '')[:500]}
CTA: {ad_data.get('cta', '')}
Format: {ad_data.get('format', 'image')}

Respond in JSON format:
{{
    "type": "promotional|educational|brand_awareness|conversion|ugc",
    "confidence": 1-10,
    "action": "study_creative|test_similar|monitor|ignore",
    "risk": "low|medium|high",
    "why": "ONE sentence explaining the psychological trigger or creative pattern"
}}

Rules for "why":
- Exactly one sentence
- No fluff or generic statements
- Name specific pattern: Hook/Angle/Offer/Creative/Social Proof/Scarcity/etc.
- Explain the psychological mechanism
- Example: "Scarcity countdown creates urgency through loss aversion, forcing immediate decision"
"""
    
    def _generate_why_fallback(self, ad_data: Dict) -> str:
        """Fallback if LLM fails"""
        return "Clear value proposition matches buyer search intent at consideration stage"


if __name__ == "__main__":
    # Test
    test_ad = {
        "brand": "TestBrand",
        "headline": "Get 50% Off - Limited Time Only!",
        "primary_text": "Join 10,000+ happy customers who transformed their business with our proven system. Sale ends tonight!",
        "cta": "Shop Now",
        "format": "image"
    }
    
    analyzer = AdAnalyzer(mode="rules")  # Use rules for testing
    result = analyzer.analyze(test_ad)
    
    print(f"Type: {result.opportunity_type}")
    print(f"Confidence: {result.confidence}/10")
    print(f"Why it works: {result.why_it_works}")
    print(f"Action: {result.action_recommendation}")
    print(f"Risk: {result.risk_level}")
