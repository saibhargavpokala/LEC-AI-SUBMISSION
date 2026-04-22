import json


class BudgetError(Exception):
    pass


class BudgetTracker:
    def __init__(self, token_cap: int = 50000, cost_cap: float = 0.50):
        self.token_cap    = token_cap
        self.cost_cap     = cost_cap
        self.total_tokens = 0
        self.total_cost   = 0.0
        self.calls        = 0

    def record(self, input_tokens: int, output_tokens: int):
        # Claude Sonnet pricing
        cost = (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

        self.total_tokens += input_tokens + output_tokens
        self.total_cost   += cost
        self.calls        += 1

        if self.total_tokens > self.token_cap:
            raise BudgetError(
                f"Token cap ({self.token_cap:,}) exceeded. "
                f"Used: {self.total_tokens:,}. "
                f"Fix: Break query into smaller parts."
            )
        if self.total_cost > self.cost_cap:
            raise BudgetError(
                f"Cost cap (${self.cost_cap}) exceeded. "
                f"Used: ${self.total_cost:.4f}."
            )

    def status(self) -> str:
        pct = round(self.total_tokens / self.token_cap * 100, 1)
        return (
            f"Tokens: {self.total_tokens:,}/{self.token_cap:,} ({pct}%) | "
            f"Cost: ${self.total_cost:.4f}/${self.cost_cap} | "
            f"Calls: {self.calls}"
        )

    def rejected_response(self, completed: list) -> str:
        return json.dumps({
            "status":    "rejected_budget_exceeded",
            "tokens":    self.total_tokens,
            "cost":      self.total_cost,
            "completed": completed,
            "message":   "Budget exceeded. Try a simpler question."
        })