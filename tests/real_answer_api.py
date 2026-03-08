"""Serve one fixed real answer for manual endpoint validation."""

from flask import Flask, jsonify, request

app = Flask(__name__)

# Real answer from the dataset for testing
REAL_ANSWER = """Source: Divrei Yoel al HaTorah, Exodus, Vayakhel 1:5

אכן יובן עפ"י הנודע דכל אדם יש לו מחלקי הקדושה נצוצות קדושות השייכים לשורשו
המצפים לתיקון על ידו, וכן הוא הדבר במקומו של אדם, ואף גם בחפציו שהוא רוכש
לעצמו יש בהם נצה"ק שמועל עליו לתקנם ולהעלותם לשרשם, ואם האדם זוכה אזי מגיעים
אליו אותם החפצים השייכים לשורשו והמצפים להיותם נתקנים על ידו, ודבר זה מבואר
בליקו"ת להאריז"ל דתכלית כל הגלויות הם לתקן ולהעלות כל ניצוצי הקדושה שנתפזרו
לבין הקליפות וכל אחד מישראל צריך לגלות במקום שבו נמצאים הנצה"ק השייכים לשרשו
ואשר עליה דידיה רמיין לתקנן ולהעלותם. וכמו"כ בחפצי האדם וברכושו יש נצה"ק
השייכים לשרשו וכמ"ש ק"ז זלה"ה בייטב לב פ' בהר דכל אדם נמשך לעסוק במסחר החביב
לו לפי שבאותו חפץ יש בו נצה"ק השייכים לנפשו ולכן יחפוץ בו, ובעסקו בו כדת של
תורה ונזהר מאזהרות שנאמרו בו איסורי אונאה ורבית וכו' אז יעלה הנצה"ק לשרשן,
יע"ש בדבה"ק באורך.

https://tashma.co.il/books/learn/19079/%D7%93%D7%91%D7%A8%D7%99_%D7%99%D7%95%D7%90%D7%9C_%D7%A2%D7%9C_%D7%94%D7%AA%D7%95%D7%A8%D7%94/%D7%91%D7%9E%D7%93%D7%91%D7%A8/%D7%A4%D7%A8%D7%A9%D7%AA_%D7%91%D7%94%D7%A2%D7%9C%D7%AA%D7%9A/%D7%9B%D7%94?line=57--%D7%91%D7%9E%D7%93%D7%91%D7%A8-%D7%A4%D7%A8%D7%A9%D7%AA+%D7%91%D7%94%D7%A2%D7%9C%D7%AA%D7%9A-%D7%9B%D7%94

See: https://www.sefaria.org/Divrei_Yoel_al_HaTorah%2C_Exodus%2C_Vayakhel.1.5
Commentary: https://www.sefaria.org/Tanya%2C_Likutei_Amarim.37
API: https://www.sefaria.org/api/texts/Divrei_Yoel_al_HaTorah.Exodus.Vayakhel.1
Edition: Standard printed edition, Brooklyn, N.Y.
Key term: https://www.sefaria.org/Klein_Dictionary%2C_%D7%A0%D6%B4%D7%99%D7%A6%D7%95%D6%B9%D7%A5
Analysis via Sefaria's interconnected library system"""


@app.route("/get_answer", methods=["POST"])
def get_answer():
    """Return a real answer from the dataset for testing"""
    data = request.get_json()
    data.get("question", "")

    # Return the real answer regardless of question for testing
    return jsonify({"answer": REAL_ANSWER})


if __name__ == "__main__":
    print("Starting Real Answer API on port 5002...")
    app.run(port=5002, debug=False)
