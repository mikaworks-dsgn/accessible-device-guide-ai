import csv
from pathlib import Path

from need_card import AXIS_OPTIONS, load_cue_rules, make_need_card


DATA_DIR = Path(__file__).resolve().parent / "data"
EVAL_PATH = DATA_DIR / "eval_sentences.csv"
RESULT_PATH = DATA_DIR / "eval_result.csv"
DICTIONARY_PATH = DATA_DIR / "cue_dictionary.csv"

AXES = list(AXIS_OPTIONS)
UNKNOWN = "不明"
SUPPORT = "案内"


def load_eval_sentences(path: Path) -> list[dict[str, str]]:
    required_columns = {"id", "文"} | {f"{axis}_正解" for axis in AXES}

    with path.open(encoding="utf-8-sig", newline="") as eval_file:
        reader = csv.DictReader(eval_file)
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError(f"評価データに必要な列がありません: {sorted(required_columns)}")
        return list(reader)


def evaluate_sentence(row: dict[str, str], rules) -> dict[str, object]:
    card = make_need_card(row["文"], rules)

    axes = {}
    for axis in AXES:
        if card["status"] == "support":
            predicted, evidence = SUPPORT, []
        else:
            predicted = card["axes"][axis]["value"]
            evidence = card["axes"][axis]["evidence"]
        correct = row[f"{axis}_正解"]
        axes[axis] = {
            "predicted": predicted,
            "correct": correct,
            "match": predicted == correct,
            "evidence": evidence,
        }

    return {"id": row["id"], "sentence": row["文"], "axes": axes}


def rate(hit: int, total: int) -> str:
    if total == 0:
        return "0/0"
    return f"{hit}/{total} ({hit / total:.1%})"


def print_summary(results: list[dict[str, object]]) -> None:
    print("■ 軸ごとの一致率")
    for axis in AXES:
        axis_results = [result["axes"][axis] for result in results]
        hits = sum(item["match"] for item in axis_results)
        known = [item for item in axis_results if item["correct"] != UNKNOWN]
        known_hits = sum(item["match"] for item in known)
        all_unknown_hits = len(axis_results) - len(known)

        print(f"- {axis}: {rate(hits, len(axis_results))}")
        print(f"    正解が不明以外の文だけ: {rate(known_hits, len(known))}")
        print(f"    参考・すべて不明と答えた場合: {rate(all_unknown_hits, len(axis_results))}")


def print_mismatches(results: list[dict[str, object]]) -> None:
    print("\n■ 一致しなかった文")
    for result in results:
        mismatched = {
            axis: item for axis, item in result["axes"].items() if not item["match"]
        }
        if not mismatched:
            continue

        print(f"【{result['id']}】{result['sentence']}")
        for axis, item in mismatched.items():
            evidence = "、".join(item["evidence"]) or "なし"
            print(
                f"  - {axis}: 判定={item['predicted']} / 正解={item['correct']}"
                f"（根拠: {evidence}）"
            )


def save_results(results: list[dict[str, object]], path: Path) -> None:
    fieldnames = ["id", "文"]
    for axis in AXES:
        fieldnames += [f"{axis}_判定", f"{axis}_正解", f"{axis}_一致", f"{axis}_根拠"]

    with path.open("w", encoding="utf-8-sig", newline="") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = {"id": result["id"], "文": result["sentence"]}
            for axis, item in result["axes"].items():
                row[f"{axis}_判定"] = item["predicted"]
                row[f"{axis}_正解"] = item["correct"]
                row[f"{axis}_一致"] = "○" if item["match"] else "×"
                row[f"{axis}_根拠"] = "、".join(item["evidence"])
            writer.writerow(row)


def main() -> None:
    rules = load_cue_rules(DICTIONARY_PATH)
    rows = load_eval_sentences(EVAL_PATH)
    results = [evaluate_sentence(row, rules) for row in rows]

    print(f"評価した文: {len(results)}文\n")
    print_summary(results)
    print_mismatches(results)
    save_results(results, RESULT_PATH)
    print(f"\n結果を保存しました: {RESULT_PATH.relative_to(RESULT_PATH.parents[1])}")


if __name__ == "__main__":
    main()
