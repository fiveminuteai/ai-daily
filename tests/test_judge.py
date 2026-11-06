"""The code fact-checker (6 Nov 2026): never rejects a true claim, never passes a broken one, on these cases."""
from fma.judge import judge

SRC = ("OpenAI says that during testing, GPT-6 Cyber went out of bounds less than 1 percent of the time, down from "
       "around 5 percent with GPT-5.6 Cyber. Today we're announcing that OpenAI will acquire Pierre Computer Company. "
       "You can guide generation combining character images and short motion clips (up to three seconds). "
       "Anthropic says access is read-only, meaning Personal Finance can't move, manage, or invest users' money. "
       "You can also specify duration in one-second increments from 3 to 15 seconds.")


def v(claim):
    return judge(claim, SRC)[0]


def test_true_claims_pass_or_go_to_a_reader():
    assert v("GPT-6 Cyber went out of bounds less than 1 percent of the time, down from around 5 percent[S1].") == "supported"
    assert v("Users can set the length in one-second steps from 3 to 15 seconds[S1].") != "unsupported"
    assert v("Personal Finance can't move, manage or invest users' money[S1].") != "unsupported"


def test_broken_claims_never_pass():
    assert v("GPT-6 Cyber went out of bounds less than 4 percent of the time[S1].") == "unsupported"    # number
    assert v("Users can add short motion clips of three seconds[S1].") == "unsupported"                # limit dropped
    assert v("OpenAI has acquired Pierre Computer Company[S1].") != "supported"                        # plan as done
    assert v("Personal Finance can move, manage and invest users' money[S1].") != "supported"          # negative lost


def test_less_counts_as_negative_but_only_does_not():
    src = ("OpenAI says GPT-6 Cyber is less likely to go rogue and hack other platforms. It is not hacking other companies. "
           "Anthropic says access is read-only, meaning Personal Finance can't move, manage, or invest users' money.")
    assert judge("It is less likely to hack[S1].", src)[0] == "supported"
    assert judge("Access is read-only: it can move, manage or invest your money[S1].", src)[0] != "supported"   # flipped
