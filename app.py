from pathlib import Path

import pandas as pd
import streamlit as st

from evaluate import AXES, evaluate_sentence, load_eval_sentences
from need_card import load_cue_rules, make_need_card


DATA_DIR = Path(__file__).resolve().parent / "data"
DICTIONARY_PATH = DATA_DIR / "cue_dictionary.csv"
EVAL_PATH = DATA_DIR / "eval_sentences.csv"
HOLDOUT_PATH = DATA_DIR / "holdout_sentences.csv"

# 例文は評価用30文から選ぶ（確認用の文は使わない）
EXAMPLE_IDS = ["6", "1", "22", "21"]


# 画面を操作するたびにファイル全体が実行し直されるので、辞書の読み込みと評価は一度だけ行う
@st.cache_resource
def get_rules():
    return load_cue_rules(DICTIONARY_PATH)


@st.cache_data
def get_examples() -> list[str]:
    rows = {row["id"]: row["文"] for row in load_eval_sentences(EVAL_PATH)}
    return [rows[example_id] for example_id in EXAMPLE_IDS]


@st.cache_data
def get_scores(path: Path) -> dict[str, str]:
    results = [evaluate_sentence(row, get_rules()) for row in load_eval_sentences(path)]
    scores = {}
    for axis in AXES:
        hits = sum(result["axes"][axis]["match"] for result in results)
        scores[axis] = f"{hits}/{len(results)}（{hits / len(results):.1%}）"
    return scores


def set_sentence(sentence: str) -> None:
    st.session_state["sentence"] = sentence


def show_card(sentence: str) -> None:
    card = make_need_card(sentence, get_rules())
    if card["status"] == "support":
        st.warning(card["message"])
        return

    with st.container(border=True):
        st.subheader("ニーズカード")
        for column, (axis, details) in zip(st.columns(3), card["axes"].items()):
            with column:
                evidence = "、".join(details["evidence"]) or "なし"
                st.caption(axis)
                st.markdown(f"**{details['value']}**")
                st.caption(f"根拠：{evidence}")

    if card["question"] is not None:
        st.info(f"確認：{card['question']}")


st.set_page_config(page_title="ニーズカード（試作）")
st.title("ニーズカード（試作）")
st.write(
    "あいまいなことばから「今求めていること」を読み取り、3つの軸で表します。"
    "人の性格や心の状態は判定しません。"
)

sentence = st.text_input("今やりたいことを書いてください", key="sentence")

st.caption("試せる例文（押すと入力欄に入ります）")
for column, example in zip(st.columns(2) * 2, get_examples()):
    column.button(example, on_click=set_sentence, args=(example,), width="stretch")

if sentence.strip():
    show_card(sentence)

st.divider()
st.subheader("評価の結果")
st.caption("3つの軸それぞれで、判定が正解と一致した文の数です。確認用の11文は、辞書やルール作りに使っていない文です。")
eval_scores = get_scores(EVAL_PATH)
holdout_scores = get_scores(HOLDOUT_PATH)
st.table(
    pd.DataFrame(
        {
            "評価用30文": [eval_scores[axis] for axis in AXES],
            "確認用11文": [holdout_scores[axis] for axis in AXES],
        },
        index=AXES,
    )
)

st.subheader("この試作の限界")
st.markdown(
    "- 辞書にあることばしか読み取れません。ボードゲームや遊園地のような、辞書にないことばは見逃します。\n"
    f"- 具体性は、評価用30文では{eval_scores['具体性']}一致しましたが、"
    f"確認用11文では{holdout_scores['具体性']}でした。"
    "「手がかりがなければ低い」というルールが、評価用の文に合わせすぎています（過学習）。\n"
    "- 確認の質問は表示するだけです。答えを選んでカードを更新することはまだできません。"
)
