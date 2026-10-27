import math

from flask import Flask, render_template, request

app = Flask(__name__)


def bmi_guidance(bmi):
    if bmi < 18.5:
        return {
            "label": "體重過輕",
            "tone": "low",
            "advice": "留意是否攝取足夠且均衡的營養，規律進食並搭配適度肌力活動；若體重下降，建議諮詢醫師或營養師。",
        }
    if bmi < 24:
        return {
            "label": "健康體位",
            "tone": "healthy",
            "advice": "維持均衡飲食與規律運動，並持續留意睡眠及生活習慣，幫助保持健康體位。",
        }
    if bmi < 27:
        return {
            "label": "體重過重",
            "tone": "high",
            "advice": "可從減少含糖飲料、增加蔬菜與日常活動量開始，循序建立適合自己的健康習慣。",
        }
    return {
        "label": "肥胖",
        "tone": "high",
        "advice": "建議與醫師或營養師討論適合自己的飲食及運動計畫，並留意血壓、血糖等健康指標。",
    }


def parse_positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def target_bmi_status(bmi, target_bmi):
    difference = round(abs(bmi - target_bmi), 1)
    if difference == 0:
        return {
            "difference": "0.0",
            "message": "恭喜你，已達到目標 BMI！",
            "tone": "goal-reached",
        }
    direction = "降低" if bmi > target_bmi else "增加"
    return {
        "difference": f"{difference:.1f}",
        "message": f"距離目標還需要{direction} {difference:.1f} BMI",
        "tone": "goal-progress",
    }


@app.route("/", methods=["GET", "POST"])
def index():
    name_input = ""
    height_input = ""
    weight_input = ""
    target_bmi_input = ""
    errors = {}
    result = None

    if request.method == "POST":
        name_input = request.form.get("name", "").strip()
        height_input = request.form.get("height", "").strip()
        weight_input = request.form.get("weight", "").strip()
        target_bmi_input = request.form.get("target_bmi", "").strip()
        height = parse_positive_number(height_input)
        weight = parse_positive_number(weight_input)
        target_bmi = None
        if target_bmi_input:
            target_bmi = parse_positive_number(target_bmi_input)
            if target_bmi is None or target_bmi < 10 or target_bmi > 50:
                errors["target_bmi"] = "請輸入 10 至 50 之間的目標 BMI。"

        if height is None:
            errors["height"] = "請輸入大於 0 的有效身高（公分）。"
        if weight is None:
            errors["weight"] = "請輸入大於 0 的有效體重（公斤）。"

        if not errors:
            height_meters = height / 100
            height_squared = height_meters * height_meters
            if not math.isfinite(height_squared) or height_squared == 0:
                errors["height"] = "無法使用這組數值計算 BMI，請檢查身高與體重。"
            else:
                bmi = weight / height_squared
                if not math.isfinite(bmi) or bmi == 0:
                    errors["weight"] = "無法使用這組數值計算 BMI，請檢查身高與體重。"
                else:
                    displayed_bmi = round(bmi, 1)
                    result = {
                        "bmi": f"{displayed_bmi:.1f}",
                        **bmi_guidance(displayed_bmi),
                    }
                    if target_bmi is not None:
                        target = round(target_bmi, 1)
                        result["target_bmi"] = f"{target:.1f}"
                        result["target_status"] = target_bmi_status(
                            displayed_bmi, target
                        )

    return render_template(
        "index.html",
        name_input=name_input,
        height_input=height_input,
        weight_input=weight_input,
        target_bmi_input=target_bmi_input,
        errors=errors,
        result=result,
    )


if __name__ == "__main__":
    app.run(debug=True)
