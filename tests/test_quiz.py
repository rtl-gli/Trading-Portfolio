from random import Random

from portfolio_research.quiz import QUESTIONS, select_question


def test_quiz_questions_have_valid_answer_indexes_and_explanations() -> None:
    assert QUESTIONS
    for question in QUESTIONS:
        assert question.prompt
        assert question.options
        assert 0 <= question.answer_index < len(question.options)
        assert question.explanation


def test_question_selection_can_be_reproduced_with_seeded_generator() -> None:
    first = select_question(Random(42))
    second = select_question(Random(42))

    assert first == second
