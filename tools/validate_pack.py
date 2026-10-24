#!/usr/bin/env python3
"""Validate (and optionally merge) FastRead bilingual packs.

    python3 tools/validate_pack.py pack.json [more.json ...]
    python3 tools/validate_pack.py --merge out.json part1.json part2.json ...

Exit code 0 = no errors (warnings are allowed), 1 = errors found.
Standard library only.
"""
import json
import sys
import unicodedata

LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
WORD_KEYS = {"w", "l", "g", "lg", "lvl", "p", "sw", "sd"}


def core(s: str) -> str:
    """Letters and digits only, lower-cased — the same key the app uses for alignment."""
    return "".join(c for c in s if unicodedata.category(c)[0] in "LN").lower()


def sentences_of(par):
    return par if isinstance(par, list) else par.get("sentences", [])


def validate(pack, name="pack"):
    errors, warnings = [], []
    E = lambda m: errors.append(f"{name}: {m}")
    W = lambda m: warnings.append(f"{name}: {m}")

    if not str(pack.get("format", "")).startswith("fastread-pack/"):
        E('"format" must be "fastread-pack/1"')
    for k in ("title", "lang", "gloss_lang"):
        if not pack.get(k):
            E(f'missing "{k}"')
    learn = pack.get("learn", pack.get("lang"))
    if learn not in (pack.get("lang"), pack.get("gloss_lang")):
        E('"learn" must equal "lang" or "gloss_lang"')
    native_text = learn != pack.get("lang")

    paras = pack.get("paragraphs")
    if not isinstance(paras, list) or not paras:
        E('"paragraphs" must be a non-empty list')
        return errors, warnings

    n_words = n_glossed = n_swaps = 0
    for pi, par in enumerate(paras):
        sents = sentences_of(par)
        if not sents:
            W(f"paragraph {pi} is empty")
        for si, s in enumerate(sents):
            loc = f"p{pi}.s{si}"
            text = s.get("text", "")
            if not text.strip():
                E(f"{loc}: empty text")
                continue
            if not s.get("tr"):
                W(f"{loc}: no sentence translation (tr)")
            words = s.get("words")
            if words is None:
                W(f"{loc}: no words[] — word modes will be empty for this sentence")
                continue
            expected = [core(t) for t in text.split() if core(t)]
            got = [core(w.get("w", "")) for w in words]
            if expected != got:
                # find first mismatch for a helpful message
                i = next((k for k, (a, b) in enumerate(zip(expected, got)) if a != b), min(len(expected), len(got)))
                E(f"{loc}: words[] do not match text tokens at #{i}: "
                  f"text has {expected[i:i+3]!r}, words has {got[i:i+3]!r} "
                  f"(text {len(expected)} tokens vs words {len(got)})")
            phrases = {}
            for wi, w in enumerate(words):
                wl = f"{loc}.w{wi}({w.get('w')!r})"
                extra = set(w) - WORD_KEYS
                if extra:
                    W(f"{wl}: unknown keys {sorted(extra)}")
                if not isinstance(w.get("g", ""), str):
                    E(f"{wl}: g must be a string")
                if w.get("lvl") and w["lvl"] not in LEVELS:
                    E(f"{wl}: lvl must be one of A1..C2")
                if w.get("g"):
                    n_glossed += 1
                    if len(w["g"]) > 40:
                        W(f"{wl}: gloss is long ({len(w['g'])} chars) — keep it under ~25")
                if w.get("p"):
                    phrases.setdefault(w["p"], set()).add(w.get("g", ""))
                if "sw" in w or "sd" in w:
                    if not w.get("sw"):
                        E(f"{wl}: sd without sw")
                    if w.get("sd") not in (1, 2, 3, 4, 5):
                        E(f"{wl}: sd must be an integer 1..5")
                    if not native_text:
                        W(f"{wl}: swaps only make sense when the text is in the native language (learn == gloss_lang)")
                    if w.get("p"):
                        E(f"{wl}: do not swap words that are part of a phrase (p)")
                    n_swaps += 1
                n_words += 1
            for p, gs in phrases.items():
                if len(gs) > 1:
                    W(f"{loc}: phrase {p!r} has different glosses on its words: {sorted(gs)}")

    if n_words:
        if native_text and n_swaps == 0:
            W("native-language text without any swaps (sw) — the 'weave' mode will be unavailable")
        if native_text and n_swaps / n_words > 0.35:
            W(f"{n_swaps}/{n_words} words have swaps — that is a lot; aim for 10–25%")
    print(f"{name}: {len(paras)} paragraphs, {n_words} words, {n_glossed} glossed, {n_swaps} swaps")
    return errors, warnings


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == "--merge":
        out, parts = argv[1], argv[2:]
        packs = [json.load(open(p, encoding="utf-8")) for p in parts]
        merged = dict(packs[0])
        merged["paragraphs"] = [par for p in packs for par in p["paragraphs"]]
        errs, warns = validate(merged, out)
        for m in warns: print("warning:", m)
        for m in errs: print("ERROR:", m)
        json.dump(merged, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {out}")
        return 1 if errs else 0
    bad = False
    for path in argv:
        try:
            pack = json.load(open(path, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: {path}: not valid JSON: {e}")
            bad = True
            continue
        errs, warns = validate(pack, path)
        for m in warns: print("warning:", m)
        for m in errs: print("ERROR:", m)
        bad |= bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
