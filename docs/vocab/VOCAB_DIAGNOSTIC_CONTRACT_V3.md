# VOCAB_DIAGNOSTIC_CONTRACT_V3

## 0. Status

This document is the canonical contract for rebuilding LinguaBot Vocab from zero.

It defines the diagnostic vocabulary bank contract only.

It does not authorize:
- runtime selector changes
- database deletion
- production rollout
- automatic item generation
- migration of legacy items
- reuse of old vocab bank artifacts

## 1. Measurement target

Vocab mode measures passive recognition of Portuguese lexical meaning by a Russian-speaking learner.

The measured signal is:

A user sees one Portuguese lexical unit and chooses the correct Russian meaning from controlled alternatives.

The test must measure lexical knowledge only.

It must not measure:
- ability to guess through Russian cognates
- ability to guess through English cognates
- ability to guess through Latin or international roots
- elimination by morphology
- elimination by grammatical category mismatch
- elimination by distractor absurdity
- elimination by answer length or specificity
- general world knowledge
- grammar knowledge
- cultural knowledge
- test-taking skill
- prior exposure to LinguaBot

## 2. Diagnostic item definition

A diagnostic vocab item is valid only if all conditions are true:

- exactly one Portuguese lemma or fixed lexical unit
- exactly one intended Russian meaning
- exactly one part of speech
- exactly one frequency bin
- exactly one certified choice pack
- no ambiguity between correct answer and distractors
- no dependency on hidden context
- no reuse from legacy bank without full re-authoring from zero

An item is not valid merely because it is linguistically correct.

An item is valid only if it produces diagnostic signal.

## 3. Allowed item shape

Each item must contain:

- `lemma`
- `pos`
- `bin_name`
- `prompt`
- `correct_choice`
- `distractor_1`
- `distractor_2`
- `distractor_3`
- `distractor_4`
- `distractor_5`
- `source_note`
- `author_note`
- `audit_status`
- `audit_reasons`

Runtime may use fewer visible distractors if UI requires it, but the bank contract stores a full controlled pack.

## 4. Hard reject rules

Reject the item immediately if any condition is true:

- Portuguese lemma is transparent to a Russian speaker
- Portuguese lemma is transparent to an English speaker
- Portuguese lemma is an obvious internationalism
- Portuguese lemma contains an obvious Latin root that gives away the answer
- correct answer can be guessed by word shape
- correct answer can be guessed by suffix or prefix
- correct answer is longer than distractors in a way that reveals it
- correct answer is more specific than distractors
- correct answer is stylistically different from distractors
- distractors are different parts of speech
- distractors are different semantic class
- distractors are absurd
- distractors are jokes or fillers
- two choices can be reasonably defended as correct
- lemma has several common meanings and the prompt does not isolate one
- item tests grammar rather than lexical meaning
- item tests phraseology rather than lexical meaning
- item tests cultural knowledge rather than lexical meaning
- item duplicates an existing certified lemma
- item came from the legacy bank and was not rebuilt manually
- item was accepted because it is “good enough”

“Good enough” means reject.

## 5. Cognate and transparency policy

Default rule:

If there is doubt, reject.

Reject if the learner can plausibly infer the answer from:
- Russian cognate
- English cognate
- international word
- Latin root
- recognizable technical term
- obvious prefix/suffix
- visual similarity to the Russian answer
- visual similarity to the English equivalent

Examples of unsafe categories:
- political/institutional internationalisms
- scientific internationalisms
- technology words
- business terms
- medical terms with Latin roots
- abstract nouns with transparent suffixes
- verbs close to English/French/Spanish forms when the meaning is inferable

A word may be common and useful but still invalid diagnostically.

## 6. Distractor contract

All distractors must be plausible to a non-knower.

All choices in one pack must match by:

- part of speech
- semantic neighborhood
- abstraction level
- approximate length
- stylistic register
- frequency class where possible
- naturalness as Russian answer options

Forbidden distractors:
- obviously unrelated words
- wrong part of speech
- comic options
- rare obscure words next to a common correct answer
- direct antonym giveaways unless all options are controlled oppositions
- near-synonyms that make the item ambiguous
- hypernyms/hyponyms that can also be defended
- choices with grammatical mismatch
- choices that differ only by morphology
- choices that make one option visibly special

## 7. POS-specific rules

### Nouns

Reject if:
- noun is a transparent internationalism
- noun denotes a globally obvious object with cognate clue
- Russian answer is much more specific than distractors
- distractors mix concrete and abstract nouns without reason

### Verbs

Reject if:
- infinitive shape gives away meaning
- distractors mix action types randomly
- aspectual Russian variants create ambiguity
- correct answer is a broad verb while distractors are narrow verbs, or reverse

### Adjectives

Reject if:
- adjective is transparent by suffix
- distractors mix physical, emotional, evaluative, and technical properties randomly
- correct answer is the only natural adjective for the implied noun

### Adverbs

Reject unless the adverb clearly measures lexical recognition.

High-risk adverbs:
- discourse markers
- frequency adverbs
- transparent manner adverbs
- short functional adverbs

Adverbs require stricter audit than nouns.

## 8. Frequency bin contract

Each item has exactly one bin:

- 1K
- 2K
- 5K
- 10K
- 20K

The bin is a selection/scoring attribute, not a quality label.

A higher-bin item is not automatically better.

A bin is invalid if:
- it is missing
- it is non-canonical
- it conflicts with the intended diagnostic difficulty
- it was copied from legacy metadata without verification

## 9. Bank pipeline

Allowed path:

candidate -> manual_authoring -> independent_audit -> certified_inventory_v3 -> active_runtime_v3

Forbidden paths:

candidate -> active_runtime_v3
legacy_bank -> active_runtime_v3
donor_source -> active_runtime_v3
generated_output -> active_runtime_v3
raw_import -> active_runtime_v3
old_vocab_items -> active_runtime_v3
old_vocab_choices -> active_runtime_v3

No item enters runtime without certification.

## 10. Audit stages

### Stage A: authoring

Author creates a candidate from scratch.

Required output:
- lemma
- intended meaning
- POS
- bin
- full choice pack
- rationale for why it is non-transparent
- rationale for why distractors are plausible

### Stage B: independent audit

Auditor must check:
- transparency
- cognates
- ambiguity
- distractor quality
- POS consistency
- frequency/bin plausibility
- duplicate lemma
- duplicate meaning pattern
- legacy contamination

### Stage C: certification

Only items with `audit_status = certified` can enter runtime.

Allowed statuses:
- candidate
- rejected
- needs_rewrite
- certified
- retired

Runtime must read only `certified`.

## 11. Runtime source contract

The selector must read only a v3 runtime source.

Allowed runtime source names:
- `vocab_items_runtime_v3`
- `vocab_certified_inventory_v3`
- equivalent explicitly documented v3 source

Forbidden runtime sources:
- `vocab_items`
- `vocab_choices`
- `vocab_items_runtime` if it is backed by legacy tables
- `vocab_item_diagnostic_audit`
- any legacy audit bridge
- any donor or candidate table

Runtime must fail closed if v3 certified coverage is insufficient.

## 12. Selector contract

The selector must:

- never read raw candidate tables
- never fallback to legacy tables
- never silently bypass certification
- preserve configured POS balance
- preserve configured bin balance
- avoid repeating items inside an attempt
- avoid excessive exposure across attempts
- log selected item id, POS, bin, and selection reason
- return no item rather than selecting uncertified material

Selector quality cannot compensate for bad bank quality.

## 13. Scoring contract

Scoring must keep separate:

- raw answer count
- correct answer count
- skipped count
- reject count
- estimated vocabulary range
- confidence
- coverage snapshot
- calibration version

Before real calibration exists, result must be marked as uncalibrated.

CEFR mapping must not be claimed as validated until separately validated.

## 14. Minimum viable v3 bank

Minimum smoke bank:
- 24 certified items
- all choice packs valid
- all items non-transparent
- all POS represented
- all selected bins explicit
- selector can complete one attempt
- insufficient-bank behavior tested

Minimum diagnostic pilot bank:
- 120 certified items
- balanced POS coverage
- at least 3 bins represented
- no legacy item reuse
- all items independently audited

Minimum serious diagnostic bank:
- 300-500 certified items
- stable POS/bin coverage
- real user response data
- item-level rejection history
- exposure monitoring
- calibration review

## 15. Legacy bank policy

Legacy vocab bank is considered contaminated.

Forbidden:
- copying legacy items
- copying legacy choices
- copying legacy item ids
- copying legacy audit statuses
- using old active flags
- using donor eligibility from old system
- using old cleanup decisions as certification

Allowed:
- using old failures as negative examples
- using schema lessons
- using selector lessons
- using QA lessons

Legacy data must not be present in the v3 runtime path.

## 16. Acceptance gate before runtime

Before any v3 runtime activation:

- `VOCAB_DIAGNOSTIC_CONTRACT_V3.md` exists
- v3 schema exists
- v3 certified inventory exists
- v3 active runtime source exists
- selector reads only v3 runtime source
- no SQL reference to legacy bank in selector path
- empty bank fails closed
- insufficient bank fails closed
- tiny certified bank smoke passes
- no old vocab item is selectable
- QA proves no legacy read path

## 17. Non-negotiable principle

Bank quality is the measurement system.

If bank quality is uncertain, the result is not diagnostic.
