"""Cost tracker for LLM usage (Gemini free tier = $0)"""
import json
from datetime import datetime
from pathlib import Path


class GroqCostTracker:
    """Track Groq API usage"""

    # Gemini free tier pricing (per 1M tokens)
    PRICING = {
        'input': 0.0,
        'output': 0.0
    }

    def __init__(self, log_file='project3_costs.json'):
        self.log_file = Path(log_file)
        self.session_costs = []
        self._load_history()

    def _load_history(self):
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = []

    def _save_history(self):
        with open(self.log_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def track_call(self, agent_name: str, input_tokens: int, output_tokens: int, description: str = ""):
        """Track a single Groq API call"""
        input_cost = (input_tokens / 1_000_000) * self.PRICING['input']
        output_cost = (output_tokens / 1_000_000) * self.PRICING['output']
        total_cost = input_cost + output_cost

        call_data = {
            'timestamp': datetime.now().isoformat(),
            'agent': agent_name,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost,
            'description': description
        }

        self.session_costs.append(call_data)
        self.history.append(call_data)
        self._save_history()

        return total_cost

    def print_session_summary(self):
        """Print cost summary for current session"""
        if not self.session_costs:
            print("No calls tracked in this session")
            return

        total_cost = sum(c['total_cost'] for c in self.session_costs)
        total_tokens = sum(c['total_tokens'] for c in self.session_costs)

        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Total API calls: {len(self.session_costs)}")
        print(f"Total tokens: {total_tokens:,}")
        print(f"Total cost: ${total_cost:.4f}")
        print("=" * 60)

        # By agent
        agents = {}
        for call in self.session_costs:
            agent = call['agent']
            if agent not in agents:
                agents[agent] = {'calls': 0, 'cost': 0}
            agents[agent]['calls'] += 1
            agents[agent]['cost'] += call['total_cost']

        print("\nBy Agent:")
        for agent, stats in agents.items():
            print(f"  {agent}: {stats['calls']} calls, ${stats['cost']:.4f}")
        print("=" * 60 + "\n")
