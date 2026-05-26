"""Natural language intent recognition."""

from paper_trading.agents.base import BaseAgent
from paper_trading.agents.deciders import (
    INTENT_RECOGNITION_SYSTEM,
    INTENT_RECOGNITION_TEMPLATE,
)

# Option number -> label
OPTION_LABELS: dict[int, str] = {
    1: "LLM Multi-Agent Trading (Dry Run)",
    2: "LLM Multi-Agent Trading (Real Orders)",
    3: "Strategy-Based Trading (Dry Run)",
    4: "Strategy-Based Trading (Real Orders)",
    5: "Backtest All Strategies",
    6: "Backtest Single Strategy",
    7: "Live Trading + Auto Backtest",
    8: "Regenerate Strategy Config",
    9: "View Alpaca Account Summary",
    10: "LLM Rebalance Frequency Analysis",
    11: "Multi-Strategy Parallel Trading",
    12: "Manage TP/SL (Attach + Status Check)",
    13: "Auto-Select Best Strategy & Trade",
}


def recognize_intent(user_text: str) -> dict:
    """Use LLM to map natural language to menu option number(s).

    Returns:
        {matched_options: [int, ...], confidence: float, reasoning: str}
    """
    decider = BaseAgent(name="IntentRecognizer", system_prompt=INTENT_RECOGNITION_SYSTEM)
    prompt = INTENT_RECOGNITION_TEMPLATE.format(user_text=user_text)
    result = decider.call_llm(prompt)

    if result is None:
        return {
            "matched_options": [],
            "confidence": 0.0,
            "reasoning": "LLM unavailable --- cannot recognize intent.",
        }

    opts = result.get("matched_options", [])
    if isinstance(opts, int):
        opts = [opts]
    opts = [int(o) for o in opts if isinstance(o, (int, float)) and 1 <= int(o) <= 13]

    return {
        "matched_options": opts,
        "confidence": float(result.get("confidence", 0.0)),
        "reasoning": str(result.get("reasoning", "")),
    }
