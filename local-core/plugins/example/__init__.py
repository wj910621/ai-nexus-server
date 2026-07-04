"""Y·NEX示例插件 - 货币转换"""

def register(manager: "PluginManager"):
    """插件入口，注册技能和API路由"""
    manager.register_skill(
        "example",         # 所属插件ID
        "convert_currency", # 技能名
        convert_currency,   # 技能函数
        "将金额从一种货币转换到另一种货币"
    )
    manager.register_api_route("example", "/api/currency/convert", convert_api)

CURRENCY_RATES = {
    "USD": 7.2, "EUR": 7.8, "GBP": 9.0,
    "JPY": 0.048, "CNY": 1.0
}

def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency not in CURRENCY_RATES or to_currency not in CURRENCY_RATES:
        return "不支持该货币"
    result = amount / CURRENCY_RATES[from_currency] * CURRENCY_RATES[to_currency]
    return f"{amount} {from_currency} = {result:.2f} {to_currency}"

def convert_api():
    from flask import request, jsonify
    amt = float(request.args.get("amount", 0))
    from_c = request.args.get("from", "USD")
    to_c = request.args.get("to", "CNY")
    return jsonify({"result": convert_currency(amt, from_c, to_c)})