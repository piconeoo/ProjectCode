from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
APP_OUTPUT_FILES = {
    "app1": "Data1.json",  # 场景学习
    "app2": "Data2.json",  # 对话助手
}

os.makedirs(DATA_FOLDER, exist_ok=True)


def save_record(app_id, data):
    filename = APP_OUTPUT_FILES.get(app_id)
    if filename is None:
        return None

    filepath = os.path.join(DATA_FOLDER, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return filepath


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "未选择文件"}), 400

        try:
            data = json.load(file.stream)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "JSON 文件格式无效"}), 400
    elif request.is_json:
        data = request.get_json()
    else:
        return jsonify({"status": "error", "message": "请求格式无效，请发送 JSON 文件或 JSON 数据。"}), 400

    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "JSON 数据必须是对象"}), 400

    app_id = data.get("app_id")
    filepath = save_record(app_id, data)
    if filepath is None:
        return jsonify({"status": "error", "message": "未知 app_id，请使用 app1 或 app2"}), 400

    filename = os.path.basename(filepath)
    return jsonify({"status": "success", "message": f"JSON 数据已保存到 Data/{filename}"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
