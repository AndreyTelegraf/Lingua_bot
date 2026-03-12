from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.vocab_runtime.review import render_review
from services.vocab_runtime.repo import get_attempt_answers

router = Router()

@router.callback_query(F.data == "vocab_review")
async def vocab_review(cb: CallbackQuery):

    answers = await get_attempt_answers(cb.from_user.id)

    text = render_review(answers)

    await cb.message.answer(text)
