# Mock Billing Adapter for P6
# Simulates deduction of virtual credits and checks budget limits

def check_goal_budget(goal):
    """
    Checks if the accumulated cost exceeds the maximum budget.
    Returns (True, None) if under budget.
    Returns (False, "Budget Exceeded") if over budget.
    """
    max_budget = float(goal.get("max_budget_eur", 10.00))
    accumulated = float(goal.get("accumulated_cost", 0.0))
    
    if accumulated >= max_budget:
        return False, f"Budget of {max_budget} EUR exceeded (Current: {accumulated} EUR)"
        
    return True, None

def deduct_task_cost(goal, task_cost):
    """
    Deducts the actual cost of a task from the goal's budget (by adding to accumulated_cost).
    """
    accumulated = float(goal.get("accumulated_cost", 0.0))
    goal["accumulated_cost"] = accumulated + float(task_cost)
    return goal["accumulated_cost"]

