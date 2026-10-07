from janome.tokenizer import Tokenizer


sentences = [
    "最近なんとなく新しいことをしたい",
    "人が多いところは苦手だけど、何か面白いことないかな",
    "たまには友達とゆっくり出かけたい",
    "一人で集中できることがしたい",
    "最近ちょっと退屈",
    "人が多いところは嫌だ",
]

tokenizer = Tokenizer()

for number, sentence in enumerate(sentences, start=1):
    print(f"\n【{number}文目】{sentence}")
    print("単語\t品詞")
    for token in tokenizer.tokenize(sentence):
        print(f"{token.surface}\t{token.part_of_speech}")
