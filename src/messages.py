"""
All user-facing reply strings for Mawid.
Every function accepts lang: str ("AR" | "EN") and returns the right version.
"""
from __future__ import annotations


def greeting(lang: str) -> str:
    if lang == "AR":
        return (
            "مرحباً! أنا مساعد حجز ساعات المكتب في جامعة أم القرى.\n"
            "أخبرني باسم الدكتور/ة اللي تريد تحجز معه/ها."
        )
    return (
        "Hello! I'm the office-hours booking assistant at Umm Al-Qura University.\n"
        "Which instructor would you like to book an appointment with?"
    )


def greeting_bilingual() -> str:
    """Bilingual welcome shown at the start before the user's language is known.
    AR and EN blocks are separated by ___BI___ so _render_reply renders each with
    the correct directionality (AR = RTL div, EN = plain markdown)."""
    return (
        "مرحباً! أنا مساعد حجز ساعات المكتب في جامعة أم القرى.\n"
        "ما اسم الدكتور/ة الذي تريد الحجز معه/ها؟"
        "\n___BI___\n"
        "Hello! I'm Mawid, the office-hours booking assistant at Umm Al-Qura University.\n"
        "Which instructor would you like to book with?"
    )


def ask_slot(slot: str, lang: str) -> str:
    prompts = {
        "instructor": {
            "AR": "مع أي دكتور/ة تريد الحجز؟",
            "EN": "Which instructor would you like to book with?",
        },
        "date": {
            "AR": "ما هو التاريخ المناسب لك؟ (مثال: الأحد القادم، أو 2026-12-07)",
            "EN": "What date works for you? (e.g. next Sunday, or 2026-12-07)",
        },
        "time": {
            "AR": "في أي وقت تريد الموعد؟ (مثال: 10:00 أو 10:30)",
            "EN": "What time would you like? (e.g. 10:00 or 10:30)",
        },
        "topic": {
            "AR": "ما موضوع الموعد؟",
            "EN": "What is the topic or reason for the appointment?",
        },
        "student_name": {
            "AR": "ما اسمك الكامل؟",
            "EN": "What is your full name?",
        },
    }
    entry = prompts.get(slot, {"AR": "أخبرني أكثر.", "EN": "Could you tell me more?"})
    return entry[lang]


def validation_error(error: str, lang: str) -> str:
    if lang == "AR":
        return f"لاحظت مشكلة: {error}\nهل تريد المحاولة مرة أخرى؟"
    return f"There's an issue: {error}\nPlease try again."


def slot_unavailable(nearest: list[str], lang: str) -> str:
    if not nearest:
        if lang == "AR":
            return "هذا الوقت محجوز ولا توجد مواعيد متاحة قريبة. جرّب وقتاً آخر."
        return "That slot is already booked and no nearby slots are available. Please try a different time."
    slots_str = " or ".join(nearest) if lang == "EN" else " أو ".join(nearest)
    if lang == "AR":
        return f"هذا الوقت محجوز. أقرب المواعيد المتاحة: {slots_str}. أيهما يناسبك؟"
    return f"That slot is already booked. Nearest available times: {slots_str}. Which works for you?"


def confirmation_summary(state: dict, lang: str) -> str:
    course = state.get("course_code") or ("غير محدد" if lang == "AR" else "not specified")
    if lang == "AR":
        return (
            "تفضل ملخص الموعد:\n\n"
            f"• الدكتور/ة: {state['instructor']}  \n"
            f"• التاريخ: {state['date']}  \n"
            f"• الوقت: {state['time']}  \n"
            f"• الموضوع: {state['topic']}  \n"
            f"• الاسم: {state['student_name']}  \n"
            f"• رمز المادة: {course}  \n\n"
            "هل تريد تأكيد الحجز؟ (نعم / لا)"
        )
    return (
        "Here is your booking summary:\n\n"
        f"• Instructor: {state['instructor']}  \n"
        f"• Date: {state['date']}  \n"
        f"• Time: {state['time']}  \n"
        f"• Topic: {state['topic']}  \n"
        f"• Name: {state['student_name']}  \n"
        f"• Course code: {course}  \n\n"
        "Shall I confirm this booking? (Yes / No)"
    )


def booking_confirmed(booking_id: str, state: dict, lang: str) -> str:
    if lang == "AR":
        return (
            f"تم الحجز بنجاح! رقم حجزك هو: **{booking_id}**\n\n"
            + _booking_json(booking_id, state)
        )
    return (
        f"Booking confirmed! Your booking ID is: **{booking_id}**\n\n"
        + _booking_json(booking_id, state)
    )


def _booking_json(booking_id: str, state: dict) -> str:
    import json
    record: dict = {
        "booking_id":   booking_id,
        "instructor":   state["instructor"],
        "date":         state["date"],
        "time":         state["time"],
        "topic":        state["topic"],
        "student_name": state["student_name"],
    }
    if state.get("course_code"):
        record["course_code"] = state["course_code"]
    return f"```json\n{json.dumps(record, indent=2, ensure_ascii=False)}\n```"


def booking_cancelled(lang: str) -> str:
    if lang == "AR":
        return "تم إلغاء الحجز. إذا احتجت مساعدة مرة أخرى، أنا هنا."
    return "Booking cancelled. Feel free to start a new booking whenever you're ready."


def off_topic(lang: str) -> str:
    if lang == "AR":
        return "أنا متخصص فقط في حجز مواعيد ساعات المكتب. هل تريد حجز موعد مع دكتور/ة؟"
    return "I can only help with booking office-hours appointments. Would you like to book one?"


def ask_what_to_change(lang: str) -> str:
    if lang == "AR":
        return "بالتأكيد. ماذا تريد تغيير؟ (مثال: التاريخ، الوقت، أو الاسم)"
    return "Of course. What would you like to change? (e.g. the date, time, or name)"


def clarification_needed(slot: str, lang: str) -> str:
    hints = {
        "time": {
            "AR": "لم أفهم الوقت. هل تقصد صباحاً أم مساءً؟ مثال: 10:00 أو 14:00",
            "EN": "I couldn't understand the time. Do you mean AM or PM? Example: 10:00 or 14:00",
        },
        "date": {
            "AR": "لم أفهم التاريخ. هل تقصد مثلاً 2026-12-07؟",
            "EN": "I couldn't understand the date. Could you use a format like 2026-12-07?",
        },
    }
    entry = hints.get(slot, {
        "AR": "لم أفهم قصدك. هل يمكنك إعادة الصياغة؟",
        "EN": "I didn't quite understand. Could you rephrase that?",
    })
    return entry[lang]


def llm_error(lang: str) -> str:
    if lang == "AR":
        return "عذراً، واجهت مشكلة في الاتصال بالنموذج. يرجى المحاولة مجدداً."
    return "Sorry, there was a problem reaching the AI model. Please try again in a moment."
