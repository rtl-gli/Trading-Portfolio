"""Short project-specific finance and research-method quiz questions."""

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class QuizQuestion:
    """One multiple-choice question with a concise teaching explanation."""

    prompt: str
    options: tuple[str, ...]
    answer_index: int
    explanation: str


QUESTIONS = (
    QuizQuestion(
        prompt="Why does the backtest delay a signal calculated from today's close?",
        options=(
            "To avoid using a price before it was observable at the signal close.",
            "To make transaction costs disappear.",
            "To increase the number of trading days.",
        ),
        answer_index=0,
        explanation=(
            "A rule needs the closing price to form today's signal. It cannot also "
            "pretend it traded earlier at that same close."
        ),
    ),
    QuizQuestion(
        prompt="What does maximum drawdown measure?",
        options=(
            "Average daily price change.",
            "The largest fall from a previous portfolio-value peak.",
            "The probability of a future loss.",
        ),
        answer_index=1,
        explanation=(
            "Maximum drawdown is the worst observed peak-to-trough decline; it is "
            "historical and depends on the selected sample."
        ),
    ),
    QuizQuestion(
        prompt="Why is choosing the best parameter set on the test period a problem?",
        options=(
            "It turns the test period into training data and overfits noise.",
            "It guarantees the strategy will underperform.",
            "It removes survivorship bias.",
        ),
        answer_index=0,
        explanation=(
            "If you inspect many settings and keep the winner, the supposedly unseen "
            "test data already influenced model selection."
        ),
    ),
    QuizQuestion(
        prompt="What is a main limitation of a fixed list of companies that exist today?",
        options=(
            "It excludes past companies that failed or left the universe.",
            "It makes prices impossible to download.",
            "It guarantees equal sector weights.",
        ),
        answer_index=0,
        explanation=(
            "This survivorship bias can make historical results look better than a "
            "genuinely point-in-time universe would."
        ),
    ),
    QuizQuestion(
        prompt="Why can a long-only Markowitz optimiser still produce poor weights?",
        options=(
            "Expected returns and covariances are estimated with noise.",
            "Diversification eliminates estimation error.",
            "Weights cannot be affected by historical data.",
        ),
        answer_index=0,
        explanation=(
            "Small errors in sample means or covariance can materially change the "
            "optimiser's chosen allocation."
        ),
    ),
)


def select_question(random_source: Random | None = None) -> QuizQuestion:
    """Return one question, optionally using a caller-supplied random generator."""
    source = random_source or Random()
    return source.choice(QUESTIONS)
