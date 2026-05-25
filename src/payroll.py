def calculate_payroll(total_hours: float, overtime_hours: float, salary_rate: float, overtime_rate: float) -> dict:
    normal_hours = max(total_hours - overtime_hours, 0.0)
    normal_pay = round(normal_hours * salary_rate, 2)
    overtime_pay = round(overtime_hours * overtime_rate, 2)
    total_pay = round(normal_pay + overtime_pay, 2)

    return {
        "normal_hours": normal_hours,
        "overtime_hours": overtime_hours,
        "normal_pay": normal_pay,
        "overtime_pay": overtime_pay,
        "total_pay": total_pay,
    }
