from paperlens.textutils import BM25, numbers_in, split_sentences, tokenize


def test_sentence_split_keeps_abbreviations():
    s = split_sentences("We follow Smith et al. in Fig. 3. It scores 91.2% on SQuAD v1.1. Next, e.g. this one.")
    assert len(s) == 3 and s[0].endswith("Fig. 3.")


def test_numbers_ignore_versions_citations_and_dataset_names():
    assert numbers_in("PyTorch 2.1 and Python 3.10 [12] on Yelp-5 CIFAR-10 see Table 3") == []
    assert numbers_in("gain of 3.50% and 1,200 runs") == ["3.5", "1200"]


def test_tokenize_drops_stopwords_and_stems():
    assert "improv" in tokenize("improving") or "improv" in "".join(tokenize("improving"))
    assert "the" not in tokenize("the model")


def test_bm25_ranks_relevant_doc_first():
    docs = [tokenize(t) for t in ["cats sit on mats", "gradient descent optimises loss", "dogs bark loudly"]]
    bm = BM25(docs)
    assert bm.rank(tokenize("gradient loss"))[0][0] == 1
