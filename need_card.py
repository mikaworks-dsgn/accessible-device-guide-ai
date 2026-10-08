import csv
from dataclasses import dataclass
from pathlib import Path

from janome.tokenizer import Tokenizer


AXIS_OPTIONS = {
    "方向": ["いつものこと", "どちらでも", "新しいこと"],
    "具体性": ["低い", "中くらい", "高い"],
    "人との関わり": ["一人で", "どちらでも", "誰かと"],
}

DISTRESS_PHRASES = ("死にたい", "消えたい", "いなくなりたい")
SUPPORT_MESSAGE = (
    "つらい気持ちを話せる窓口があります。厚生労働省の"
    "『まもろうよ こころ』（https://www.mhlw.go.jp/mamorouyokokoro/）で、"
    "電話やSNSの相談先を探せます。"
)

INVERSE_VALUES = {
    ("方向", "新しいこと"): "いつものこと",
    ("方向", "いつものこと"): "新しいこと",
    ("人との関わり", "一人で"): "誰かと",
    ("人との関わり", "誰かと"): "一人で",
}


@dataclass(frozen=True)
class CueRule:
    pattern: tuple[str, ...]
    group: str
    axis: str
    value: str


@dataclass(frozen=True)
class CueMatch:
    rule: CueRule
    surface: str
    start: int
    end: int
    segment: int


@dataclass
class AxisCue:
    value: str
    evidence: list[str]
    segment: int
    start: int


def load_cue_rules(path: Path) -> list[CueRule]:
    required_columns = {"照合する並び", "グループ", "軸", "判定"}
    rules = []

    with path.open(encoding="utf-8-sig", newline="") as dictionary_file:
        reader = csv.DictReader(dictionary_file)
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError(f"辞書に必要な列がありません: {sorted(required_columns)}")

        for line_number, row in enumerate(reader, start=2):
            pattern = tuple(row["照合する並び"].split("|"))
            if not all(pattern):
                raise ValueError(f"辞書の{line_number}行目に空の照合語があります")
            rules.append(
                CueRule(
                    pattern=pattern,
                    group=row["グループ"],
                    axis=row["軸"],
                    value=row["判定"],
                )
            )

    return rules


def find_cue_matches(
    tokens: list[str], rules: list[CueRule]
) -> list[CueMatch]:
    raw_matches = []
    for start in range(len(tokens)):
        for rule in rules:
            end = start + len(rule.pattern)
            if tuple(tokens[start:end]) == rule.pattern:
                raw_matches.append((rule, start, end))

    conjunction_ends = sorted(
        {
            end
            for rule, _start, end in raw_matches
            if rule.group == "逆接"
        }
    )

    matches = []
    for rule, start, end in raw_matches:
        segment = sum(conjunction_end <= start for conjunction_end in conjunction_ends)
        matches.append(
            CueMatch(
                rule=rule,
                surface="".join(tokens[start:end]),
                start=start,
                end=end,
                segment=segment,
            )
        )

    return sorted(matches, key=lambda match: (match.start, match.end))


def make_need_card(sentence: str, rules: list[CueRule]) -> dict[str, object]:
    distress_match = next(
        (phrase for phrase in DISTRESS_PHRASES if phrase in sentence),
        None,
    )
    if distress_match is not None:
        return {"status": "support", "message": SUPPORT_MESSAGE}

    tokens = [token.surface for token in Tokenizer().tokenize(sentence)]
    matches = find_cue_matches(tokens, rules)
    cues_by_axis: dict[str, list[AxisCue]] = {
        axis: [] for axis in AXIS_OPTIONS
    }

    for match in matches:
        rule = match.rule
        if rule.group == "逆接":
            continue

        if rule.group == "評価":
            if rule.value == "避けたい":
                prior_cues = [
                    (axis, cue)
                    for axis, axis_cues in cues_by_axis.items()
                    for cue in axis_cues
                    if cue.start < match.start
                    and (axis, cue.value) in INVERSE_VALUES
                ]
                if prior_cues:
                    target_axis, target = max(
                        prior_cues,
                        key=lambda item: item[1].start,
                    )
                    target.value = INVERSE_VALUES[(target_axis, target.value)]
                    if match.surface not in target.evidence:
                        target.evidence.append(match.surface)
            continue

        if rule.axis in cues_by_axis and rule.value in AXIS_OPTIONS[rule.axis]:
            cues_by_axis[rule.axis].append(
                AxisCue(
                    value=rule.value,
                    evidence=[match.surface],
                    segment=match.segment,
                    start=match.start,
                )
            )

    axes = {}
    for axis, options in AXIS_OPTIONS.items():
        axis_cues = cues_by_axis[axis]
        if axis_cues:
            latest_segment = max(cue.segment for cue in axis_cues)
            selected = max(
                (cue for cue in axis_cues if cue.segment == latest_segment),
                key=lambda cue: cue.start,
            )
            axes[axis] = {
                "value": selected.value,
                "evidence": selected.evidence,
            }
        else:
            axes[axis] = {"value": "不明", "evidence": []}

    unknown_axis = next(
        (axis for axis, result in axes.items() if result["value"] == "不明"),
        None,
    )
    question = None
    if unknown_axis is not None:
        choices = "／".join(AXIS_OPTIONS[unknown_axis])
        question = f"{unknown_axis}について、どれに近いですか？（{choices}）"

    return {"status": "card", "axes": axes, "question": question}


def main() -> None:
    dictionary_path = Path(__file__).resolve().parent / "data" / "cue_dictionary.csv"
    rules = load_cue_rules(dictionary_path)
    sentences = [
        "最近なんとなく新しいことをしたい",
        "人が多いところは苦手だけど、何か面白いことないかな",
        "たまには友達とゆっくり出かけたい",
        "一人で集中できることがしたい",
        "最近ちょっと退屈",
        "人が多いところは嫌だ",
        "最近ちょっと消えたい",
    ]

    for number, sentence in enumerate(sentences, start=1):
        print(f"\n【{number}文目】{sentence}")
        result = make_need_card(sentence, rules)
        if result["status"] == "support":
            print(result["message"])
            continue

        for axis, details in result["axes"].items():
            evidence = "、".join(details["evidence"]) or "なし"
            print(f"- {axis}: {details['value']}（根拠: {evidence}）")
        if result["question"] is not None:
            print(f"確認: {result['question']}")


if __name__ == "__main__":
    main()
